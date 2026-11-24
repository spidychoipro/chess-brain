"""Windows 제목표시줄을 앱 다크 테마에 맞춘다.

Qt가 그리는 클라이언트 영역은 그대로 두고, OS가 그리는 제목표시줄과
테두리만 어둡게 맞춘다. 프레임을 직접 만들지 않아서 스냅/최소화 같은
기본 동작은 그대로 살아 있다.
"""
from __future__ import annotations


def apply_modern_window(window) -> None:
    import sys

    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = int(window.winId())
        if not hwnd:
            return

        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
        ]
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long

        def set_attr(attr: int, value: int) -> bool:
            val = wintypes.DWORD(value)
            rc = dwm.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), attr, ctypes.byref(val), ctypes.sizeof(val)
            )
            return rc == 0

        # 어두운 제목표시줄. 구버전 빌드는 속성 번호가 19였다.
        for attr in (20, 19):
            if set_attr(attr, 1):
                break

        # 얇은 테두리도 카드 색에 맞춘다 (Windows 11).
        set_attr(34, 0x00473831)  # BORDER #313847 -> COLORREF

        # Mica 배경은 지원되는 빌드에서만 적용된다.
        set_attr(38, 2)
    except Exception:
        pass
