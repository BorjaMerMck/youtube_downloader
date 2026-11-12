"""Pruebas offline con red, Whisper y señales simulados. No requieren Qt.

Desde la raíz del proyecto: python -m unittest discover -s tests -p test_playlists.py -v
"""
import ast
import importlib.util
import itertools
import os
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Job:
    url: str
    out_dir: str
    do_video: bool
    do_audio: bool
    do_transcribe: bool
    max_height: int | None = None


class Signal:
    def __init__(self):
        self.events = []
        self.callback = None

    def emit(self, *args):
        self.events.append(args)
        if self.callback:
            self.callback(*args)


class Signals:
    def __init__(self):
        for name in ('log', 'progress', 'status', 'stages', 'busy'):
            setattr(self, name, Signal())


def load_service():
    # Importa el archivo real en un paquete aislado, simulando solo dependencias.
    modules = {}
    for name in ('playlist_testpkg', 'playlist_testpkg.services',
                 'playlist_testpkg.signals', 'playlist_testpkg.models'):
        modules[name] = types.ModuleType(name)
        modules[name].__path__ = []
    for name in ('yt_dlp', 'yt_dlp.utils', 'playlist_testpkg.config',
                 'playlist_testpkg.signals.signals', 'playlist_testpkg.models.models'):
        modules[name] = types.ModuleType(name)
    modules['yt_dlp'].YoutubeDL = Mock()
    modules['yt_dlp.utils'].DownloadError = type('DownloadError', (Exception,), {})
    config = modules['playlist_testpkg.config']
    config.TRANSCRIBE_MAX_MINUTES = 0
    config.WhisperModel = Mock()
    config.find_ffmpeg = lambda: None
    modules['playlist_testpkg.signals.signals'].Signals = Signals
    modules['playlist_testpkg.models.models'].Job = Job
    spec = importlib.util.spec_from_file_location(
        'playlist_testpkg.services.service', ROOT / 'app/services/service.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


service_module = load_service()


class PlaylistTests(unittest.TestCase):
    def setUp(self):
        self.signals = Signals()
        self.service = service_module.MediaService(self.signals)
        self.items = [{'id': f'video_{i}', 'title': f'Título {i}'} for i in range(3)]
        self.service.fetch_playlist_items = Mock(return_value=self.items)
        self.service.download_video = Mock(side_effect=lambda url, out, **kw: url + '.mp4')
        self.service.download_audio_mp3 = Mock(side_effect=lambda url, out: url + '.mp3')
        self.service.transcribe_to_txt = Mock(side_effect=lambda audio: audio + '.txt')
        self.job = Job('https://www.youtube.com/playlist?list=demo', '.', False, False, True)

    def test_text_only_playlist_and_global_progress(self):
        outputs = self.service.run_job(self.job)
        self.assertEqual(len(outputs), 6)
        self.assertEqual(self.service.transcribe_to_txt.call_count, 3)
        self.assertEqual(self.signals.stages.events[-1], (6, 6, ''))
        self.assertTrue(any('Vídeo 2/3' in e[2] for e in self.signals.stages.events))
        self.service.fetch_playlist_items.assert_called_once_with(
            self.job.url, limit=0, reset_cancel=False)
        for call in self.service.download_audio_mp3.call_args_list:
            self.assertNotIn('list=', call.args[0])

    def test_all_option_combinations_single_and_playlist(self):
        for flags in itertools.product([False, True], repeat=3):
            if not any(flags):
                continue
            for playlist in (False, True):
                with self.subTest(flags=flags, playlist=playlist):
                    self.setUp()
                    job = replace(self.job, do_video=flags[0], do_audio=flags[1], do_transcribe=flags[2],
                                  url=self.job.url if playlist else 'https://youtu.be/single')
                    count = 3 if playlist else 1
                    steps = int(flags[0]) + int(flags[1] or flags[2]) + int(flags[2])
                    outputs = self.service.run_job(job)
                    self.assertEqual(len(outputs), count * steps)
                    self.assertEqual(self.signals.stages.events[-1], (count * steps, count * steps, ''))

    def test_empty_playlist_is_error(self):
        self.service.fetch_playlist_items.return_value = []
        with self.assertRaisesRegex(RuntimeError, 'vacía'):
            self.service.run_job(self.job)

    def test_no_300_video_limit(self):
        self.service.fetch_playlist_items.return_value = [{'id': f'v{i}'} for i in range(301)]
        self.service.run_job(self.job)
        self.assertEqual(self.service.transcribe_to_txt.call_count, 301)
        self.assertEqual(self.signals.stages.events[-1], (602, 602, ''))

    def test_cancel_between_videos_does_not_reset(self):
        def cancel(completed, total, label):
            if completed == 2:
                self.service.request_cancel()
        self.signals.stages.callback = cancel
        with self.assertRaises(service_module.CancelledError):
            self.service.run_job(self.job)
        self.assertEqual(self.service.download_audio_mp3.call_count, 1)
        self.assertEqual(self.service.transcribe_to_txt.call_count, 1)

    def test_cancel_during_listing(self):
        def listing(*args, **kwargs):
            self.service.request_cancel()
            return self.items
        self.service.fetch_playlist_items.side_effect = listing
        with self.assertRaises(service_module.CancelledError):
            self.service.run_job(self.job)
        self.service.download_audio_mp3.assert_not_called()

    def test_error_identifies_video_and_does_not_claim_completion(self):
        self.service.transcribe_to_txt.side_effect = ['first.txt', RuntimeError('fallo simulado')]
        with self.assertRaisesRegex(RuntimeError, 'Vídeo 2/3'):
            self.service.run_job(self.job)
        completed = [e[0] for e in self.signals.stages.events if not e[2]]
        self.assertEqual(completed, [1, 2, 3])
        self.assertEqual(self.service.download_audio_mp3.call_count, 2)

    def test_keep_resolution_and_output_folder(self):
        self.service.run_job(replace(self.job, do_video=True, max_height=720, out_dir='salida'))
        self.assertTrue(all(call.args[1] == 'salida' and call.kwargs['max_height'] == 720
                            for call in self.service.download_video.call_args_list))

    def test_url_fallback_strips_list(self):
        for item in ({'url': 'https://www.youtube.com/watch?v=abc&list=demo'},
                     {'url': 'https://youtu.be/abc?list=demo'}, {'url': 'abc'}):
            self.assertEqual(self.service._playlist_video_url(item), 'https://www.youtube.com/watch?v=abc')
        with self.assertRaises(RuntimeError):
            self.service._playlist_video_url({'title': 'Sin ID'})

    def test_real_file_writing_reuses_model_and_releases_it(self):
        service = service_module.MediaService(self.signals)
        service.fetch_playlist_items = Mock(return_value=self.items)
        model = Mock()
        model.transcribe.side_effect = lambda *a, **kw: (
            iter([types.SimpleNamespace(text=' Texto de prueba ', end=1)]), None)
        constructor = Mock(return_value=model)
        with tempfile.TemporaryDirectory() as folder, patch.object(service_module, 'WhisperModel', constructor):
            paths = [str(Path(folder) / f'{i}.mp3') for i in range(3)]
            service.download_audio_mp3 = Mock(side_effect=paths)
            service.run_job(replace(self.job, out_dir=folder))
            for i in range(3):
                self.assertEqual((Path(folder) / f'{i}.txt').read_text(), 'Texto de prueba\n')
        constructor.assert_called_once_with('small', device='cpu', compute_type='int8')
        self.assertIsNone(service._whisper_model)

    def test_cancelled_txt_is_removed(self):
        service = service_module.MediaService(self.signals)
        def segments():
            yield types.SimpleNamespace(text='Primera línea', end=1)
            service.request_cancel()
            yield types.SimpleNamespace(text='No escribir', end=2)
        model = Mock()
        model.transcribe.return_value = (segments(), None)
        with tempfile.TemporaryDirectory() as folder, patch.object(service_module, 'WhisperModel', return_value=model):
            audio = str(Path(folder) / 'audio.mp3')
            with self.assertRaises(service_module.CancelledError):
                service.transcribe_to_txt(audio)
            self.assertFalse(Path(audio).with_suffix('.txt').exists())


class SelectionTests(unittest.TestCase):
    def test_text_only_can_select_whole_playlist_or_single_video(self):
        tree = ast.parse((ROOT / 'app/ui/ui.py').read_text())
        app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'App')
        fn = next(n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == '_build_job_or_show_error')
        for pure_playlist, answer in itertools.product((False, True), (0, 1)):
            with self.subTest(pure_playlist=pure_playlist, answer=answer):
                message = Mock(Yes=1, No=0)
                message.question.return_value = answer
                ns = {'Job': Job, 'QMessageBox': message, 'WhisperModel': object()}
                exec(compile(ast.Module(body=[fn], type_ignores=[]), 'selection', 'exec'), ns)
                playlist = 'https://www.youtube.com/playlist?list=demo'
                single = 'https://www.youtube.com/watch?v=video'
                ui = Mock(out_dir='out')
                ui.url_input.text.return_value = playlist if pure_playlist else single + '&list=demo'
                ui._normalize_youtube_url.return_value = playlist if pure_playlist else single
                ui._extract_playlist_url.return_value = playlist
                ui.service._is_playlist_url.return_value = pure_playlist
                ui.chk_video.isChecked.return_value = False
                ui.chk_audio.isChecked.return_value = False
                ui.chk_transcribe.isChecked.return_value = True
                result = ns['_build_job_or_show_error'](ui)
                if pure_playlist and answer == 0:
                    self.assertIsNone(result)
                else:
                    self.assertTrue(result.do_transcribe)
                    self.assertEqual(result.url, playlist if answer else single)
                ui.chk_transcribe.setChecked.assert_not_called()


if __name__ == '__main__':
    unittest.main()
