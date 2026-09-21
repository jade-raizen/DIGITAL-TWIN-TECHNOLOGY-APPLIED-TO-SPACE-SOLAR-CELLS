#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
SIMULATION — simulation/run_simulation.py (v1.0, BILINGUE)
Simulation Runner: Integrates all models for a complete mission simulation
===============================================================================
"""
from __future__ import annotations
import numpy as np
import sys
from pathlib import Path

# Ajout du dossier models au path
sys.path.insert(0, str(Path(__file__).parent.parent / "models"))

from config import *
from radiation_model import selection_conservatrice, predire_degradation
from thermal_model import corriger_temperature, vieillissement_thermal
from annealing_model import run_recuit
from electrical_model import extraire_diode
from tj_model import current_matching_3j
from mission_model import charger_profil_mission

__version__ = "1.0"

# =============================================================================
# 1. SIMULATION COMPLÈTE / COMPLETE SIMULATION
# =============================================================================
def run_simulation_complete(cellule, profil_mission, fluences):
    """[FR] Simulation complète d'une cellule sur une mission.
    [EN] Complete cell simulation over a mission."""
    resultats = {
        "cellule": cellule.get("ref", "UNKNOWN"),
        "mission": profil_mission.get("nom", "UNKNOWN"),
        "fluences": [],
        "predictions": [],
    }
    
    for flu in fluences:
        # Dégradation radiative
        pred = {}
        for g in ("Voc", "Isc", "Vmp", "Imp"):
            v_bol = cellule.get(g, [None])[0]
            C, Phi0 = cellule.get("C", {}).get(g), cellule.get("Phi0", {}).get(g)
            if v_bol is not None and C is not None and Phi0 is not None:
                pred[g] = predire_degradation(v_bol, C, Phi0, flu)
            else:
                pred[g] = None
        
        resultats["fluences"].append(flu)
        resultats["predictions"].append(pred)
    
    return resultats

# =============================================================================
# 2. MAIN / ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    print(f"🚀 run_simulation.py v{__version__}")
    print("   Simulation complète d'une cellule solaire spatiale")
    
    # Exemple : 3G30C sur LEO 15 ans
    cellule = {
        "ref": "3G30C",
        "Voc": [2.700], "Isc": [0.5202], "Vmp": [2.411], "Imp": [0.5044],
        "C": {"Voc": 0.021, "Isc": 0.015, "Vmp": 0.025, "Imp": 0.018},
        "Phi0": {"Voc": 7.9e13, "Isc": 1.0e14, "Vmp": 8.5e13, "Imp": 9.0e13},
    }
    profil = {"nom": "LEO_ISS", "orbite": "LEO", "duree_annees": 15.0}
    fluences = [0, 1e13, 1e14, 1e15]
    
    res = run_simulation_complete(cellule, profil, fluences)
    print(f"\n   Résultats pour {res['cellule']} sur {res['mission']} :")
    for i, flu in enumerate(res["fluences"]):
        pred = res["predictions"][i]
        if pred["Voc"] is not None:
            print(f"   Φ = {flu:.1e} e/cm² → Voc = {pred['Voc']:.3f} V")