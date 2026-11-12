"""Ejecuta las pruebas de playlists con un informe legible en español.

Guarda este archivo junto a las carpetas app/ y tests/.
Uso: python debug.py
Solo cambia la presentación: las pruebas existentes siguen siendo las mismas.
"""
from pathlib import Path
import sys
import shutil
import textwrap
import time
import unittest


NOMBRES = {
    "test_all_option_combinations_single_and_playlist": "Opciones de vídeo, audio y texto",
    "test_cancel_between_videos_does_not_reset": "Cancelar entre vídeos detiene la playlist",
    "test_cancel_during_listing": "Cancelar mientras se consulta la playlist",
    "test_cancelled_txt_is_removed": "Eliminar el TXT incompleto al cancelar",
    "test_empty_playlist_is_error": "Detectar una playlist vacía",
    "test_error_identifies_video_and_does_not_claim_completion": "Indicar qué vídeo falla sin anunciar éxito",
    "test_keep_resolution_and_output_folder": "Respetar la calidad y la carpeta elegidas",
    "test_no_300_video_limit": "Procesar listas de más de 300 vídeos",
    "test_real_file_writing_reuses_model_and_releases_it": "Guardar los TXT y reutilizar el modelo",
    "test_text_only_playlist_and_global_progress": "Transcribir toda la playlist y mostrar su progreso",
    "test_url_fallback_strips_list": "Procesar cada enlace como un vídeo individual",
    "test_text_only_can_select_whole_playlist_or_single_video": "Elegir entre un vídeo y la playlist completa",
}


def nombre(prueba):
    identificador = prueba.id().rsplit(".", 1)[-1]
    return NOMBRES.get(identificador, identificador.replace("test_", "", 1).replace("_", " "))


def imprimir_tabla(filas):
    """Tabla sin dependencias externas, adaptada al ancho de la terminal."""
    ancho = shutil.get_terminal_size(fallback=(90, 24)).columns
    anchos = (4, max(22, min(60, ancho - 30)), 16)
    def borde(izquierda, union, derecha):
        print(izquierda + union.join("─" * (n + 2) for n in anchos) + derecha)
    def fila(valores):
        celdas = [textwrap.wrap(str(valor), width=n) or [""]
                  for valor, n in zip(valores, anchos)]
        for linea in range(max(map(len, celdas))):
            print("│ " + " │ ".join(
                (celda[linea] if linea < len(celda) else "").ljust(n)
                for celda, n in zip(celdas, anchos)
            ) + " │")
    borde("┌", "┬", "┐")
    fila(("N.º", "Comprobación", "Resultado"))
    borde("├", "┼", "┤")
    for valores in filas:
        fila(valores)
    borde("└", "┴", "┘")


class ResultadoLegible(unittest.TestResult):
    def __init__(self, total):
        super().__init__()
        self.total = total
        self.correctas = 0
        self.estados = {}

    def startTest(self, test):
        super().startTest(test)
        self.estados[test] = "EN CURSO"

    def addSuccess(self, test):
        super().addSuccess(test)
        self.correctas += 1
        self.estados[test] = "CORRECTO"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.estados[test] = "FALLO: el resultado no es el esperado"

    def addError(self, test, err):
        super().addError(test, err)
        self.estados[test] = "ERROR: no se pudo completar la comprobación"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.estados[test] = f"OMITIDA: {reason}"

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.estados[test] = "FALLO ESPERADO: pendiente de resolver"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.estados[test] = "REVISAR: pasó una prueba marcada como fallo esperado"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.estados[test] = "FALLO: una de las variantes no ha superado la prueba"

    def stopTest(self, test):
        super().stopTest(test)

    def resumen(self, segundos, interrumpido=False):
        imprimir_tabla([
            (f"{indice:02d}", nombre(test), estado.split(":", 1)[0])
            for indice, (test, estado) in enumerate(self.estados.items(), start=1)
        ])
        print()
        print("RESUMEN DE LAS COMPROBACIONES\n")
        print(f"  Pruebas ejecutadas:  {self.testsRun} de {self.total}")
        print(f"  Correctas:          {self.correctas}")
        print(f"  Fallos detectados:  {len(self.failures)}")
        print(f"  Errores:            {len(self.errors)}")
        print(f"  Omitidas:           {len(self.skipped)}")
        print(f"  Duración:           {segundos:.3f} segundos")
        if self.expectedFailures:
            print(f"  Fallos esperados:   {len(self.expectedFailures)}")
        if self.unexpectedSuccesses:
            print(f"  Éxitos inesperados: {len(self.unexpectedSuccesses)}")

        if interrumpido:
            print("\nCOMPROBACIONES INTERRUMPIDAS. No se han ejecutado todas.")
        elif self.wasSuccessful() and self.correctas == self.total:
            print("\nRESULTADO: TODAS LAS PRUEBAS HAN PASADO.")
        elif self.wasSuccessful():
            print("\nRESULTADO: SIN FALLOS INESPERADOS. Revisa las pruebas omitidas o pendientes.")
        else:
            print("\nRESULTADO: HAY PROBLEMAS QUE REVISAR.")

        if self.failures or self.errors:
            print("\nDETALLES PARA DIAGNOSTICAR EL PROBLEMA\n")
            for tipo, incidencias in (("FALLO", self.failures), ("ERROR", self.errors)):
                for test, detalle in incidencias:
                    print(f"{tipo}: {nombre(test)}\n{test.id()}\n{detalle}")
        for test in self.unexpectedSuccesses:
            print(f"\nRevisa la marca expectedFailure de: {test.id()}")
        for test, motivo in self.skipped:
            print(f"\nOmitida: {nombre(test)}. Motivo: {motivo}")
        print("\nEstas pruebas simulan las descargas y el modelo de transcripción.")
        print("La prueba con vídeos reales se hace por separado en la aplicación.\n")


def main():
    root = Path(__file__).resolve().parent
    carpeta = root / "tests"
    print("\nYOUTUBE DOWNLOADER\nComprobaciones de playlists\n")
    if not (carpeta / "test_playlists.py").is_file():
        print("No se encuentra tests/test_playlists.py.")
        print("Coloca debug.py en la raíz del proyecto, junto a app y tests.")
        return 2
    # Permite arrancar el script desde otra carpeta o mediante una ruta absoluta.
    sys.path.insert(0, str(root))
    try:
        suite = unittest.TestLoader().discover(str(carpeta), pattern="test_playlists.py")
    except Exception as exc:
        print(f"No se pudieron cargar las pruebas: {exc}")
        return 2
    total = suite.countTestCases()
    if not total:
        print("No se han encontrado pruebas. No se puede confirmar ningún resultado.")
        return 2
    print(f"Ejecutando {total} comprobaciones…\n", flush=True)
    resultado = ResultadoLegible(total)
    inicio = time.perf_counter()
    interrumpido = False
    try:
        suite.run(resultado)
    except KeyboardInterrupt:
        interrumpido = True
    resultado.resumen(time.perf_counter() - inicio, interrumpido)
    if interrumpido:
        return 130
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
