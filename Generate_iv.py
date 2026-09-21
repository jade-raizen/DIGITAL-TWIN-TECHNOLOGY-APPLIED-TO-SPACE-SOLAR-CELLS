#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
SCRIPT GÉNÉRATION I-V — scripts/generate_iv.py (v1.0, BILINGUE)
Generate I-V curves for a given cell and conditions
===============================================================================
"""
from __future__ import annotations
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "models"))

from config import *
from electrical_model import extraire_diode, courbe_iv

__version__ = "1.0"

def generer_iv(voc, isc, vmp, imp, t_k, ns=3):
    """[FR] Génère la courbe I-V complète. [EN] Generates full I-V curve."""
    d = extraire_diode(voc, isc, vmp, imp, t_k, ns)
    if d is None:
        return None
    vv, iv, pv = courbe_iv(d, voc, t_k, ns)
    return {"V": vv, "I": iv, "P": pv, "params": d}

if __name__ == "__main__":
    print(f"📈 generate_iv.py v{__version__}")
    # Exemple 3G30C BOL
    res = generer_iv(2.700, 0.5202, 2.411, 0.5044, T_REF_K, ns=3)
    if res:
        print(f"   Points I-V : {len(res['V'])}")
        print(f"   P_max = {max(res['P']):.4f} W")