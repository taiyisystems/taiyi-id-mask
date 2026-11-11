"""taiyi-id-mask：繁體中文（台灣）文字的個資偵測與遮蔽。"""
from .core import (Finding, MaskResult, PIIBlocked, age_band, guard, mask, minimize_record, scan,
                   unmask)

__version__ = '1.1.0'
__all__ = ['Finding', 'MaskResult', 'PIIBlocked', 'age_band', 'guard', 'mask', 'minimize_record', 'scan',
           'unmask', '__version__']
