"""
Ponto de entrada do aplicativo Controle CAD — SolidWorks.
Inicializa o ambiente Windows (DPI awareness), configura logs e abre a interface gráfica.
"""

import sys
import os

# Garante que o diretório de execução seja a pasta do projeto (evita C:\Windows\system32 ao executar por atalho/duplo clique)
DIRETORIO_PROJETO = os.path.dirname(os.path.abspath(__file__))
os.chdir(DIRETORIO_PROJETO)
if DIRETORIO_PROJETO not in sys.path:
    sys.path.insert(0, DIRETORIO_PROJETO)

import traceback
from core.logger import registrar_log


def configurar_ambiente_windows():
    """Configura o Windows para exibir a interface em alta resolução (High DPI)."""
    if sys.platform == "win32":
        try:
            import ctypes
            # Habilita DPI Awareness por monitor no Windows 10/11
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main():
    configurar_ambiente_windows()

    try:
        from ui.app import ControleCADApp
        app = ControleCADApp()
        app.mainloop()
    except Exception as e:
        erro_detalhado = traceback.format_exc()
        print("Erro fatal na execução do Controle CAD:")
        print(erro_detalhado)
        registrar_log(
            "ERRO FATAL NA APLICAÇÃO",
            {"Erro": str(e), "Traceback": erro_detalhado},
            nivel="ERROR"
        )
        try:
            import tkinter.messagebox as mb
            mb.showerror(
                "Erro Inesperado",
                f"Ocorreu um erro ao executar o Controle CAD:\n\n{e}\n\nOs detalhes foram gravados no arquivo controle_cad.log."
            )
        except Exception:
            pass


if __name__ == "__main__":
    main()
