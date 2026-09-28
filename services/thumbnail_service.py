"""
Serviço de Miniaturas e Previews 3D para o Controle CAD.
Extrai diretamente as miniaturas 3D reais de arquivos do SolidWorks (.SLDPRT / .SLDASM / .SLDDRW)
usando a API nativa do Windows Shell (IShellItemImageFactory), processa o enquadramento da geometria
e armazena em cache de alta velocidade para CustomTkinter.
"""

import os
import ctypes
from ctypes import wintypes, POINTER, Structure, c_void_p, c_long, byref, HRESULT, sizeof
from typing import Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageOps
import customtkinter as ctk

from core.models import PecaInfo


# --- Estruturas COM do Windows Shell para extração de miniaturas nativas ---
class _GUID(Structure):
    _fields_ = [
        ('Data1', wintypes.DWORD),
        ('Data2', wintypes.WORD),
        ('Data3', wintypes.WORD),
        ('Data4', wintypes.BYTE * 8)
    ]


class _SIZE(Structure):
    _fields_ = [('cx', c_long), ('cy', c_long)]


class _BITMAPINFOHEADER(Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]


class _BITMAP(Structure):
    _fields_ = [
        ('bmType', wintypes.LONG),
        ('bmWidth', wintypes.LONG),
        ('bmHeight', wintypes.LONG),
        ('bmWidthBytes', wintypes.LONG),
        ('bmPlanes', wintypes.WORD),
        ('bmBitsPixel', wintypes.WORD),
        ('bmBits', wintypes.LPVOID)
    ]


# IID_IShellItemImageFactory: {bcc18b79-ba16-442f-80c4-8a59c30c463b}
_IID_IShellItemImageFactory = _GUID(
    0xbcc18b79, 0xba16, 0x442f,
    (wintypes.BYTE * 8)(0x80, 0xc4, 0x8a, 0x59, 0xc3, 0x0c, 0x46, 0x3b)
)


class ThumbnailService:
    def __init__(self):
        # Cache em memória para objetos CTkImage (chave: (caminho_arquivo, largura, altura))
        self._cache_ctk: Dict[Tuple[str, int, int], ctk.CTkImage] = {}
        self._inicializar_com()

    def _inicializar_com(self):
        """Inicializa subsistema OLE/COM no thread atual."""
        try:
            ctypes.windll.ole32.CoInitialize(None)
        except Exception:
            pass

    def localizar_arquivo_cad(self, peca: PecaInfo) -> Optional[str]:
        """Localiza o arquivo .SLDPRT ou .SLDASM da peça."""
        if not peca.pasta_path or not os.path.exists(peca.pasta_path):
            return None

        # 1. Pasta CAD/
        pasta_cad = os.path.join(peca.pasta_path, "CAD")
        if os.path.exists(pasta_cad):
            for f in os.listdir(pasta_cad):
                f_up = f.upper()
                if (f_up.endswith(".SLDPRT") or f_up.endswith(".SLDASM")) and not f.startswith("~$"):
                    return os.path.join(pasta_cad, f)

        # 2. Raiz da pasta da peça
        for f in os.listdir(peca.pasta_path):
            f_up = f.upper()
            if (f_up.endswith(".SLDPRT") or f_up.endswith(".SLDASM")) and not f.startswith("~$"):
                return os.path.join(peca.pasta_path, f)

        return None

    def extrair_thumbnail_windows(self, caminho_arquivo: str, width: int = 512, height: int = 512) -> Optional[Image.Image]:
        """Extrai a miniatura 3D nativa em alta resolução usando o Windows Shell."""
        if not caminho_arquivo or not os.path.exists(caminho_arquivo):
            return None

        try:
            shell32 = ctypes.windll.shell32
            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32

            pItem = c_void_p()
            hr = shell32.SHCreateItemFromParsingName(
                wintypes.LPCWSTR(caminho_arquivo),
                None,
                byref(_IID_IShellItemImageFactory),
                byref(pItem)
            )
            if hr != 0 or not pItem:
                return None

            vtable = ctypes.cast(pItem, POINTER(POINTER(c_void_p))).contents
            GetImageFunc = ctypes.WINFUNCTYPE(
                HRESULT, c_void_p, _SIZE, wintypes.DWORD, POINTER(wintypes.HBITMAP)
            )(vtable[3])
            ReleaseFunc = ctypes.WINFUNCTYPE(wintypes.ULONG, c_void_p)(vtable[2])

            hbmp = wintypes.HBITMAP()
            size = _SIZE(width, height)
            # SIIGBF_BIGGERSIZEOK = 0x1 (permite extrair tamanho total do thumbnail em alta resolução)
            hr = GetImageFunc(pItem, size, 0x1, byref(hbmp))
            ReleaseFunc(pItem)

            if hr != 0 or not hbmp:
                return None

            # Conversão HBITMAP -> PIL Image
            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

            bm = _BITMAP()
            gdi32.GetObjectW(hbmp, sizeof(_BITMAP), byref(bm))
            w, h = bm.bmWidth, bm.bmHeight

            if w <= 0 or h <= 0:
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)
                gdi32.DeleteObject(hbmp)
                return None

            bmi = _BITMAPINFOHEADER()
            bmi.biSize = sizeof(_BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down DIB
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buf = (ctypes.c_byte * (w * h * 4))()
            gdi32.GetDIBits(hdc_mem, hbmp, 0, h, byref(buf), byref(bmi), 0)

            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            gdi32.DeleteObject(hbmp)

            img = Image.frombuffer('RGBA', (w, h), bytes(buf), 'raw', 'BGRA', 0, 1)
            return img
        except Exception as e:
            print(f"Aviso ao extrair miniatura do Shell para {caminho_arquivo}: {e}")
            return None

    def obter_caminho_thumbnail(self, peca: PecaInfo) -> Optional[str]:
        """Retorna o caminho do arquivo de preview se existir no disco."""
        if not peca.pasta_path:
            return None

        locais = [
            os.path.join(peca.pasta_path, "preview.png"),
            os.path.join(peca.pasta_path, "CAD", "preview.png"),
            os.path.join(peca.pasta_path, "preview_3d.png"),
        ]
        for loc in locais:
            if os.path.exists(loc):
                return loc
        return None

    def obter_image_pil(self, peca: PecaInfo, size: Tuple[int, int] = (190, 110)) -> Image.Image:
        """
        Carrega a miniatura 3D real da peça.
        Se não existir ou se o arquivo CAD tiver sido atualizado, extrai diretamente do arquivo .SLDPRT/.SLDASM.
        """
        w, h = size
        caminho_preview = self.obter_caminho_thumbnail(peca)
        caminho_cad = self.localizar_arquivo_cad(peca)

        # Verifica se o arquivo CAD foi modificado após o preview.png
        precisa_extrair = False
        if not caminho_preview or not os.path.exists(caminho_preview):
            precisa_extrair = True
        elif caminho_cad and os.path.exists(caminho_cad):
            try:
                mtime_cad = os.path.getmtime(caminho_cad)
                mtime_prev = os.path.getmtime(caminho_preview)
                if mtime_cad > mtime_prev:
                    precisa_extrair = True
            except Exception:
                pass

        if precisa_extrair and caminho_cad:
            raw_img = self.extrair_thumbnail_windows(caminho_cad, width=768, height=576)
            if raw_img:
                try:
                    # Salva o preview na pasta da peça
                    preview_destino = os.path.join(peca.pasta_path, "preview.png")
                    raw_img.save(preview_destino, "PNG")
                    caminho_preview = preview_destino
                except Exception:
                    pass

        # Se temos o preview (arquivo salvo ou acabou de ser extraído)
        if caminho_preview and os.path.exists(caminho_preview):
            try:
                raw_img = Image.open(caminho_preview).convert("RGBA")
                return self._processar_preview_cad(raw_img, size, peca)
            except Exception as e:
                print(f"Aviso ao processar preview de {peca.codigo}: {e}")

        # Fallback: cria o visualizador 3D isométrico
        return self._criar_placeholder_3d(peca.codigo, peca.tipo, size)

    def _processar_preview_cad(self, raw_img: Image.Image, size: Tuple[int, int], peca: PecaInfo) -> Image.Image:
        """
        Enquadra a geometria 3D com inteligência:
        1. Remove margens vazias da viewport recortando ao redor do modelo real.
        2. Aplica escala proporcional suave (Lanczos).
        3. Renderiza sobre um fundo de estúdio CAD com cantos arredondados e moldura sutil.
        """
        w, h = size

        # Detecta geometria excluindo pixels de fundo branco/cinza uniforme
        bg_diff = ImageOps.invert(raw_img.convert("RGB"))
        bbox = bg_diff.getbbox()

        # Se a imagem for toda branca (peça nova vazia que ainda não foi modelada)
        if not bbox:
            return self._criar_placeholder_3d(peca.codigo, peca.tipo, size, subtitulo="Novo 3D")

        # Recorta com respiro de 6% ao redor do modelo 3D real
        bx0, by0, bx1, by1 = bbox
        bw = bx1 - bx0
        bh = by1 - by0

        # Se o modelo tem dimensões reais
        if bw > 10 and bh > 10:
            pad_x = int(bw * 0.06)
            pad_y = int(bh * 0.06)
            bx0 = max(0, bx0 - pad_x)
            by0 = max(0, by0 - pad_y)
            bx1 = min(raw_img.width, bx1 + pad_x)
            by1 = min(raw_img.height, by1 + pad_y)
            cropped = raw_img.crop((bx0, by0, bx1, by1))
        else:
            cropped = raw_img

        # Redimensiona proporcionalmente mantendo proporção (Contain)
        cropped.thumbnail((w - 8, h - 8), Image.Resampling.LANCZOS)

        # Fundo do estúdio CAD suave e limpo
        final_canvas = Image.new("RGBA", (w, h), (242, 245, 248, 255))

        # Centraliza a peça
        offset_x = (w - cropped.width) // 2
        offset_y = (h - cropped.height) // 2
        final_canvas.paste(cropped, (offset_x, offset_y), cropped if cropped.mode == "RGBA" else None)

        # Máscara com cantos arredondados
        radius = 8
        mask = Image.new("L", (w, h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle([0, 0, w, h], radius=radius, fill=255)

        output = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        output.paste(final_canvas, (0, 0), mask)

        # Borda técnica sutil
        draw_out = ImageDraw.Draw(output)
        draw_out.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, outline=(65, 80, 100, 180), width=1)

        return output

    def obter_ctk_image(self, peca: PecaInfo, size: Tuple[int, int] = (64, 48)) -> ctk.CTkImage:
        """Retorna um CTkImage pronto para uso em labels e botões com cache de alta performance."""
        cache_key = (peca.codigo, size[0], size[1])

        if cache_key in self._cache_ctk:
            return self._cache_ctk[cache_key]

        pil_img = self.obter_image_pil(peca, size=size)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        self._cache_ctk[cache_key] = ctk_img
        return ctk_img

    def limpar_cache(self, peca: Optional[PecaInfo] = None):
        """Limpa o cache de imagens para forçar recarregamento."""
        if peca is None:
            self._cache_ctk.clear()
        else:
            keys_to_del = [k for k in self._cache_ctk if k[0] == peca.codigo]
            for k in keys_to_del:
                del self._cache_ctk[k]

    def _criar_placeholder_3d(self, codigo: str, tipo: str, size: Tuple[int, int], subtitulo: str = "3D") -> Image.Image:
        """Desenha um bloco isométrico 3D estilizado com visual de software de engenharia CAD."""
        w, h = size
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)

        is_assembly = (tipo.lower() == "montagem")
        is_co = (tipo.upper() == "CO")

        # Fundo do cartão da miniatura com cantos arredondados
        if is_co:
            bg_color = (42, 36, 26, 255)
            border_color = (150, 105, 40, 255)
        elif is_assembly:
            bg_color = (42, 34, 48, 255)
            border_color = (110, 65, 145, 255)
        else:
            bg_color = (32, 38, 48, 255)
            border_color = (55, 85, 125, 255)

        draw.rounded_rectangle([1, 1, w - 2, h - 2], radius=8, fill=bg_color, outline=border_color, width=1)

        # Geometria isométrica 3D central
        cx = w // 2
        cy = h // 2 - 2
        cw = max(8, min(w // 4, 28))
        ch = max(5, int(cw * 0.58))

        pt_top = (cx, cy - ch)
        pt_right = (cx + cw, cy)
        pt_center = (cx, cy + ch)
        pt_left = (cx - cw, cy)

        # Cores das faces 3D (iluminação realista)
        if is_co:
            cor_topo = (235, 150, 45, 255)
            cor_esquerda = (190, 110, 25, 255)
            cor_direita = (145, 80, 15, 255)
            cor_arestas = (255, 205, 120, 255)
        elif is_assembly:
            cor_topo = (160, 90, 220, 255)
            cor_esquerda = (115, 55, 170, 255)
            cor_direita = (80, 35, 130, 255)
            cor_arestas = (200, 150, 255, 255)
        else:
            cor_topo = (70, 140, 220, 255)
            cor_esquerda = (40, 95, 170, 255)
            cor_direita = (25, 70, 130, 255)
            cor_arestas = (130, 185, 255, 255)

        # Face Superior (Top)
        draw.polygon([pt_top, pt_right, pt_center, pt_left], fill=cor_topo, outline=cor_arestas)

        # Face Esquerda (Left)
        pt_bottom_left = (cx - cw, cy + ch + ch)
        pt_bottom_center = (cx, cy + ch + ch + ch)
        draw.polygon([pt_left, pt_center, pt_bottom_center, pt_bottom_left], fill=cor_esquerda, outline=cor_arestas)

        # Face Direita (Right)
        pt_bottom_right = (cx + cw, cy + ch + ch)
        draw.polygon([pt_center, pt_right, pt_bottom_right, pt_bottom_center], fill=cor_direita, outline=cor_arestas)

        # Texto pequeno no canto inferior
        draw.text((w // 2, h - 8), subtitulo, fill=(160, 180, 205, 255), anchor="mm")

        return im
