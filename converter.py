#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
CONVERTISSEUR EXPERT UNIFIÉ — converter.py (v28 FUSIONNÉ, BILINGUE)
YAML ↔ JSON ↔ Excel + EXPORT SOLAIRE SPÉCIALISÉ + MENU SPYDER
+ PROVENANCE (F2/F4/S2) + F3 (fluence structurée) + F5 (R_sh + seuil)
+ M22 (dommages) + M18 (recuit) + M23 (sous-cellules) + CRYO (mission)
===============================================================================
[FR] TROIS MODES DANS UN SEUL FICHIER :
1) GÉNÉRIQUE : conversion YAML ↔ JSON ↔ Excel (détection auto, aplatissement).
2) SOLAIRE : si le YAML contient `cellules_physique` (ou `--solar`), export
   spécialisé type Space_Solar_Cells_Complete_Database.xlsx :
   • 1 ligne par (cellule × fluence), 92 colonnes + colonnes provenance ;
   • colonnes calculées : Jsc, Jmp, Pmp, FF, η1367, η1353, ratios EOL/BOL,
     coeffs thermiques interpolés, diode 1-diode (I_pv, I₀, R_s, N_a) [32,33] ;
   • [v27-F4] colonne « Component Type » (bare_cell / wafer / CIC / assembly) ;
   • [v27-F2] colonne « Provenance élec » (measured / manufacturer-derived) ;
   • [v27-S2] colonnes « Poids TC » / « Source TC » ;
   • [v28-F3] colonnes « Radiation_* » structurées (particule, énergie, unité,
     fluence absolue, fluence_type, RDC mesuré depuis Rapport RT3 CDS) ;
   • [v28-F5] colonnes « R_sh », « Erreur Ajustement », « Poids Confiance »,
     « Statut Diode » + seuil de rejet 5 % ;
   • [v28-M22] colonnes dommages 8 canaux (rad, thermal, age, opt, mech, ESD,
     impact, TJ) + D_total_Pmp + D_stable ;
   • [v28-M18] colonnes recuit (A, Ea, familles) ;
   • [v28-M23] colonnes sous-cellules 3J (top/middle/bottom, current matching) ;
   • [v28-CRYO] colonne profil mission (LEO/GEO/JUICE/MARS) + flag LLL/cryo ;
   • 11 feuilles : ALL_Data_KNIME, TJ_GaAs_30pct, QJ_GaAs_32pct, Silicon,
     Thermal_Coefficients, Degradation_EOL_BOL, Damage_Channels,
     Annealing_Data, Subcells_3J, Mission_Profiles, LEGENDE_SOURCES ;
   • couleurs par technologie + niveau de dégradation + profil mission.
3) MENU : boucle interactive (Spyder/terminal).

[EN] THREE MODES IN ONE FILE: generic YAML/JSON/Excel conversion, specialized
     solar export (auto-detected or --solar) with provenance columns (F2/F4/S2),
     F3 structured radiation columns, F5 R_sh + rejection threshold, v28
     damage/annealing/subcell/mission columns, and an interactive Spyder menu.

HISTORIQUE / HISTORY
   v1  : convertisseur générique (bug dict doublon)
   v2  : fusion avec yaml_to_excel + export solaire 7 feuilles
   v3  : correctif row.update() (plus de TypeError)
   v27 : ajout F2/F4/S2 (provenance élec + Component Type + Poids/Source TC)
   v28 : FUSION COMPLÈTE :
         + F3 (fluence structurée {particule, énergie, unité})
         + F5 (R_sh + seuil de rejet 5 % + poids confiance)
         + M22 (8 canaux de dommages) + M18 (recuit 9 mécanismes)
         + M23 (sous-cellules 3J) + CRYO (profils mission)
         + 11 feuilles Excel (4 nouvelles)
         + Menu [5] Statut F3

CORRECTIFS v3 / v3 FIXES :
   • Construction par row.update() (pas de TypeError doublons).

AJOUTS v27 / v27 ADDITIONS :
   • [F4] Component Type (bare_cell / wafer / CIC / assembly).
   • [F2] Provenance élec (measured / manufacturer-derived).
   • [S2] Poids TC / Source TC (datasheet=1.0 / interpolé / extrapolé / repli).

NOUVEAUTÉS v28 / v28 ADDITIONS :
   • [F3] Colonnes Radiation_* structurées (particule, énergie, fluence_type,
     RDC mesuré depuis Rapport RT3 CDS : 2.66 pour 3MeV p, 9.03 pour 9.5MeV p).
   • [F5] SEUIL_REJET = 5 % : si erreur d'ajustement > 5 %, statut = REJETÉ.
   • [F5] R_sh optionnel (si I-V complète disponible).
   • [F5] Modèle 2-diodes LLL pour irradiance < 200 W/m² (mode cryogénique).
   • [M22] 8 canaux de dommage + composition multiplicative.
   • [M18] Recuit & récupération (9 mécanismes REC_007–REC_047).
   • [M23] Sous-cellules 3J + current matching (Kirchhoff série).
   • [CRYO] Mode cryogénique Deep Space (JUICE, Europa Clipper, Mars).

USAGE / USAGE
   python converter.py data.yaml data.json              # générique
   python converter.py table.xlsx out.yaml --flatten    # générique aplati
   python converter.py solar_cells_database.yaml out.xlsx  # solaire (auto)
   python converter.py any.yaml out.xlsx --solar        # solaire forcé
   python converter.py                                  # menu interactif

RÉFÉRENCES / REFERENCES
   [31] Tada et al., JPL 82-69 (1982).
   [32] Jain & Kapoor (2004).
   [33] Corless et al. (Lambert W, 1996).
   [34] ECSS-E-ST-20-08C Rev.2 (2023).
   [36] Baur & Bett, IEEE PVSC (2010).
   [37] Imaizumi et al., Prog. Photovolt. 25(2), 161-174 (2017).
   [105] Rival & Mandeville, Space Debris 1(1), 37-48 (1999).
   [107] Paul & Berthoud, AIAA (1995).
   RT3   Rapport RT3 CDS 25.DING.ING.PCCEC (RDC protonique 2.66, 9.03).
   SRC   Space_Solar_Cells_Complete_Database.xlsx (structure 76 colonnes).
===============================================================================
"""
import json, sys, argparse, re
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import numpy as np

try:
    import yaml
except ImportError:
    print("⚠️  pip install pyyaml"); sys.exit(1)

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font
except ImportError:
    print("⚠️  pip install openpyxl"); sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("⚠️  pip install pandas"); sys.exit(1)

try:
    from scipy.special import lambertw
except ImportError:
    lambertw = None  # diode désactivée si absente / disabled if missing

__version__ = "28"

# =============================================================================
# PARTIE 1 — CONVERTISSEUR GÉNÉRIQUE / GENERIC CONVERTER
# =============================================================================
class FileFormat(Enum):
    YAML = "yaml"; YML = "yml"; JSON = "json"; XLSX = "xlsx"; XLS = "xls"

@dataclass
class ConversionConfig:
    source_file: Path
    output_file: Path
    source_format: FileFormat = None
    output_format: FileFormat = None
    indent: int = 2
    flatten: bool = False
    verbose: bool = False

class DataConverter:
    """[FR] Convertisseur universel YAML/JSON/Excel. [EN] Universal converter."""

    def __init__(self, cfg: ConversionConfig):
        self.cfg = cfg
        self.data = None

    @staticmethod
    def detect_format(p: Path) -> FileFormat:
        m = {'.yaml': FileFormat.YAML, '.yml': FileFormat.YAML,
             '.json': FileFormat.JSON, '.xlsx': FileFormat.XLSX,
             '.xls': FileFormat.XLS}
        if p.suffix.lower() not in m:
            raise ValueError(f"❌ Format non reconnu: {p.suffix}")
        return m[p.suffix.lower()]

    def read_yaml(self, p):
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def read_json(self, p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def read_excel(self, p):
        xl = pd.ExcelFile(p)
        return {s: pd.read_excel(p, sheet_name=s)
                  .where(pd.notna(pd.read_excel(p, sheet_name=s)), None)
                  .to_dict("records") for s in xl.sheet_names}

    def write_yaml(self, d, p):
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(d, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, indent=self.cfg.indent)

    def write_json(self, d, p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=self.cfg.indent, ensure_ascii=False, default=str)

    def write_excel(self, d, p):
        """[FR] Écrit un classeur (header ligne 1, données dès ligne 2).
        [EN] Writes a workbook (header row 1, data from row 2)."""
        wb = openpyxl.Workbook(); wb.remove(wb.active)
        sheets = d.items() if isinstance(d, dict) else [("Données", d)]
        for name, data in sheets:
            df = pd.DataFrame(data if isinstance(data, list) else [data])
            ws = wb.create_sheet(str(name)[:31])
            for ci, col in enumerate(df.columns, 1):
                ws.cell(1, ci, col).font = Font(bold=True)
            for ri, row in enumerate(df.values, 2):
                for ci, v in enumerate(row, 1):
                    ws.cell(ri, ci, v)
        wb.save(p)

    def flatten_dict(self, d, parent="", sep="."):
        items = []
        for k, v in d.items():
            nk = f"{parent}{sep}{k}" if parent else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, nk, sep).items())
            elif isinstance(v, list):
                items.append((nk, json.dumps(v)))
            else:
                items.append((nk, v))
        return dict(items)

    def convert(self):
        sf = self.cfg.source_format or self.detect_format(self.cfg.source_file)
        self.data = {FileFormat.YAML: self.read_yaml, FileFormat.YML: self.read_yaml,
                     FileFormat.JSON: self.read_json}.get(sf, self.read_excel)(self.cfg.source_file)
        if self.cfg.flatten and isinstance(self.data, dict):
            self.data = self.flatten_dict(self.data)
        of = self.cfg.output_format or self.detect_format(self.cfg.output_file)
        {FileFormat.YAML: self.write_yaml, FileFormat.YML: self.write_yaml,
         FileFormat.JSON: self.write_json}.get(of, self.write_excel)(self.data, self.cfg.output_file)
        print(f"🎉 Conversion réussie : {self.cfg.source_file} → {self.cfg.output_file}")

# =============================================================================
# PARTIE 2 — EXPORT SOLAIRE / SOLAR EXPORT
# =============================================================================
K_B, Q = 1.380649e-23, 1.60217663e-19
S1367, S1353 = 136.7, 135.3  # mW/cm²

# [v28-F5] Seuil de rejet d'ajustement / Rejection threshold
SEUIL_REJET = 0.05  # 5% d'erreur max sur P_max

# [v28-CRYO] Profils de mission / Mission profiles
PROFILS_MISSION = {
    "LEO_STANDARD":  dict(distance_AU=1.0,  irradiance_W_m2=1367.0,
                         annealing=True,  diode_model="1-diode", damage_corr=1.0),
    "GEO_STANDARD":  dict(distance_AU=1.0,  irradiance_W_m2=1367.0,
                         annealing=True,  diode_model="1-diode", damage_corr=1.0),
    "JUICE_JUPITER": dict(distance_AU=5.2,  irradiance_W_m2=50.0,
                         annealing=False, diode_model="2-diode", damage_corr=1.25),
    "MARS_SURFACE":  dict(distance_AU=1.52, irradiance_W_m2=590.0,
                         annealing=False, diode_model="2-diode", damage_corr=1.10),
}

# [v28-M22] Canaux de dommage / Damage channels
STATUT_CANAL = {
    "rad":     "PARTIALLY_REVERSIBLE",
    "thermal": "PRACTICALLY_IRREVERSIBLE",
    "age":     "PRACTICALLY_IRREVERSIBLE",
    "opt":     "PRACTICALLY_IRREVERSIBLE",
    "mech":    "FUNDAMENTALLY_IRREVERSIBLE",
    "ESD":     "FUNDAMENTALLY_IRREVERSIBLE",
    "impact":  "FUNDAMENTALLY_IRREVERSIBLE",
    "TJ":      "PRACTICALLY_IRREVERSIBLE",
}

# [v28-M22] Matrice d'effet / Effect matrix
PARAMS_ELEC = ("Voc", "Isc", "Vmp", "Imp", "FF", "Rs", "Rsh")
MATRICE_EFFET = {
    "rad":     (0.9,  0.9,  0.9,  0.9,  0.7,  0.05, 0.05),
    "thermal": (0.05, 0.05, 0.5,  0.5,  0.6,  0.6,  0.05),
    "age":     (0.05, 0.05, 0.05, 0.05, 0.05, 0.7,  0.05),
    "opt":     (0.05, 0.95, 0.5,  0.5,  0.1,  0.05, 0.05),
    "mech":    (0.05, 0.6,  0.5,  0.5,  0.6,  0.6,  0.05),
    "ESD":     (0.5,  0.5,  0.5,  0.5,  0.9,  0.05, 0.95),
    "impact":  (0.05, 0.7,  0.4,  0.4,  0.5,  0.05, 0.05),
    "TJ":      (0.5,  0.05, 0.5,  0.5,  0.5,  0.7,  0.05),
}

# [v28-F3] RDC mesurés (Rapport RT3 CDS) / Measured RDC (RT3 CDS report)
RDC_MESURES = {
    ("proton", 3.0): 2.66,   # RDC 3MeV p → 1MeV e
    ("proton", 9.5): 9.03,   # RDC 9.5MeV p → 1MeV e
}

# [v28-F3] Facteur de conversion legacy (flu × 1e14) / Legacy conversion factor
FACTEUR_LEGACY = 1e14

TECH_COLORS = {"TJ": "D6E4F0", "3G30": "C8E6FA", "QJ": "D5E8D4", "3T34": "FFF2CC",
               "Si": "F8CECC", "XTJ": "E1D5E7", "ZTJ": "DAE8FC", "TER": "F5F5F5"}

MISSION_COLORS = {
    "LEO_STANDARD":  "C6EFCE",
    "GEO_STANDARD":  "BDD7EE",
    "JUICE_JUPITER": "D9D9D9",
    "MARS_SURFACE":  "F4B183",
}

def tech_color(ref, tech, terr):
    """[FR] Couleur par technologie. [EN] Color by technology."""
    if terr:
        return TECH_COLORS["TER"]
    r = (ref or "").upper()
    if tech == "QJ": return TECH_COLORS["QJ"]
    if tech == "Si": return TECH_COLORS["Si"]
    if "3T34" in r: return TECH_COLORS["3T34"]
    if "XTJ" in r or "XTE" in r: return TECH_COLORS["XTJ"]
    if "ZTJ" in r: return TECH_COLORS["ZTJ"]
    if "3G30" in r: return TECH_COLORS["3G30"]
    return TECH_COLORS["TJ"]

def deg_color(f):
    """[FR] Couleur par niveau de dégradation (fluence legacy ×10^14).
    [EN] Color by degradation level (legacy fluence ×10^14)."""
    if f <= 0:  return "FFFFFF"
    if f < 1:   return "FFFDE7"
    if f < 10:  return "FFF3E0"
    return "FCE4EC"

# =============================================================================
# [v28-F3] FONCTIONS FLUENCE STRUCTURÉE / STRUCTURED FLUENCE FUNCTIONS
# =============================================================================
def parser_chaine_rad(rad_str):
    """[FR] Parse la chaîne rad legacy (ex: "1MeV e-", "3MeV p+") en
    (particule, energie_MeV). Retourne ("electron", 1.0) par défaut.
    [EN] Parses legacy rad string into (particle, energy_MeV)."""
    if not rad_str:
        return "electron", 1.0
    rad_lower = str(rad_str).lower()
    if any(k in rad_lower for k in ("p+", "proton")):
        particule = "proton"
    elif any(k in rad_lower for k in ("n", "neutron")):
        particule = "neutron"
    elif any(k in rad_lower for k in ("ion", "heavy")):
        particule = "heavy_ion"
    else:
        particule = "electron"
    m = re.search(r"([\d.]+)\s*MeV", str(rad_str), re.IGNORECASE)
    energie = float(m.group(1)) if m else 1.0
    return particule, energie


def extraire_radiation(c):
    """[FR] Extrait la radiation structurée (v8) ou convertit flu/rad (v7).
    Retourne un dict unique (première radiation de la liste).
    [EN] Extracts structured radiation (v8) or converts flu/rad (v7).
    Returns a single dict (first radiation in the list)."""
    # CAS 1 : champ "radiation" structuré (v8)
    rad = c.get("radiation")
    if rad is not None:
        if isinstance(rad, dict):
            rad = [rad]
        if isinstance(rad, list) and len(rad) > 0:
            r0 = rad[0]
            particule = r0.get("particule", "electron")
            energie = r0.get("energie_MeV", 1.0)
            fluence = r0.get("fluence")
            if isinstance(fluence, (int, float)):
                fluence = [fluence]
            if isinstance(fluence, np.ndarray):
                fluence = fluence.tolist()
            unit = r0.get("unit", "e/cm²")
            flu_type = r0.get("fluence_type", "experimental")
            rdc = r0.get("rdc_vers_1MeV_e")
            # Lookup RDC mesuré si proton et rdc non fourni
            if rdc is None and particule == "proton":
                for (p, e), rdc_val in RDC_MESURES.items():
                    if p == "proton" and abs(e - energie) < 0.5:
                        rdc = rdc_val
                        break
            return {
                "particule": particule,
                "energie_MeV": float(energie),
                "fluence": fluence if fluence is not None else [],
                "unit": unit,
                "fluence_type": flu_type,
                "rdc": rdc,
            }

    # CAS 2 : backward compatible v7 (flu + rad)
    flu = c.get("flu") or [0.0]
    rad_str = c.get("rad") or "1MeV e-"
    particule, energie = parser_chaine_rad(rad_str)
    fluence_absolue = [f * FACTEUR_LEGACY for f in flu]
    unit = "e/cm²" if particule == "electron" else (
        "p/cm²" if particule == "proton" else (
        "n/cm²" if particule == "neutron" else "ion/cm²"))
    rdc = None
    if particule == "proton":
        for (p, e), rdc_val in RDC_MESURES.items():
            if abs(e - energie) < 0.5:
                rdc = rdc_val
                break
    return {
        "particule": particule,
        "energie_MeV": float(energie),
        "fluence": fluence_absolue,
        "unit": unit,
        "fluence_type": "experimental",
        "rdc": rdc,
    }


def fluence_legacy(c, i):
    """[FR] Retourne la fluence legacy (multiplicateur ×10^14) pour l'index i.
    [EN] Returns legacy fluence (×10^14 multiplier) for index i."""
    rad = extraire_radiation(c)
    fluence = rad.get("fluence", [])
    if not fluence or i >= len(fluence):
        return None
    return fluence[i] / FACTEUR_LEGACY

# =============================================================================
# DIODE + INTERPOLATION TC / DIODE + TC INTERPOLATION
# =============================================================================
def extraire_diode(voc, isc, vmp, imp, t_k, ns=3):
    """[FR] 1-diode (Lambert W), entrées SI. [EN] 1-diode (Lambert W), SI inputs."""
    if lambertw is None:
        return None
    v1 = (K_B * t_k) / Q
    best = (1e9, None)
    for nat in np.linspace(ns * .8, ns * 2.5, 60):
        vt = nat * v1
        if vt < 1e-4:
            continue
        i0 = isc / (np.exp(np.clip(voc / vt, -80, 80)) - 1)
        if i0 <= 1e-20 or not np.isfinite(i0):
            continue
        ipv = isc + i0 * (np.exp(np.clip(isc * .01 / vt, -80, 80)) - 1)
        al = 1 + (ipv - imp) / i0
        if al <= 1:
            continue
        rs = (vt * np.log(al) - vmp) / imp
        if rs < 1e-5 or rs > 2:
            continue
        vv = np.linspace(0, voc, 300)
        aw = (i0 * rs / vt) * np.exp(np.clip((vv + (ipv + i0) * rs) / vt, -80, 80))
        w = np.real(lambertw(np.nan_to_num(aw, nan=0., posinf=1e8, neginf=-1 / np.e)))
        iv = np.maximum(ipv + i0 - (vt / rs) * w, 0.)
        pv = vv * iv
        im = int(np.argmax(pv))
        e = abs(pv[im] - vmp * imp) / (vmp * imp) if vmp * imp > 0 else 1.0
        if e < best[0]:
            best = (e, dict(I_pv=ipv, I_0=i0, R_s=rs, N_a=nat / ns, P_max=pv[im]))
    return best[1]


def extraire_diode_v28(voc, isc, vmp, imp, t_k, ns=3, iv_complete=None):
    """[v28-F5] Extraction diode avec seuil de rejet + R_sh optionnel.
    [EN] Diode extraction with rejection threshold + optional R_sh."""
    d = extraire_diode(voc, isc, vmp, imp, t_k, ns)
    if d is None:
        return {"statut": "NON_IDENTIFIABLE", "raison": "Pas de solution physique",
                "poids_confiance": 0.0}

    # Erreur sur P_max
    pmp_calcule = vmp * imp
    erreur = abs(d["P_max"] - pmp_calcule) / pmp_calcule if pmp_calcule > 0 else 1.0

    # SEUIL DE REJET
    if erreur > SEUIL_REJET:
        return {"statut": "REJETE", "erreur": erreur,
                "raison": f"Erreur {erreur:.1%} > seuil {SEUIL_REJET:.0%}",
                "poids_confiance": 0.0}

    # R_sh optionnel (si I-V complète)
    if iv_complete is not None:
        V_arr, I_arr = iv_complete
        n_pts = min(5, len(V_arr))
        if n_pts >= 2:
            pente = np.polyfit(V_arr[:n_pts], I_arr[:n_pts], 1)[0]
            d["R_sh"] = 1.0 / pente if pente > 0 else None
        else:
            d["R_sh"] = None
    else:
        d["R_sh"] = None

    # Poids de confiance lié à l'erreur
    if erreur < 0.01:
        poids = 1.0
    elif erreur < SEUIL_REJET:
        poids = 0.5
    else:
        poids = 0.0

    d["statut"] = "actif"
    d["erreur"] = erreur
    d["poids_confiance"] = poids
    return d


def extraire_diode_2d_v28(voc, isc, vmp, imp, t_k, ns=3, iv_complete=None):
    """[v28-F5] Extraction 2-diodes pour LLL (< 200 W/m²).
    [EN] 2-diode extraction for LLL (< 200 W/m²)."""
    d = extraire_diode_v28(voc, isc, vmp, imp, t_k, ns, iv_complete)
    if d["statut"] != "actif":
        return d
    # I_02 estimé (heuristic : 1% de I_01) — NON_IDENTIFIABLE sans I-V complète
    if iv_complete is not None:
        V_arr, I_arr = iv_complete
        vt = (K_B * t_k) / Q
        I_1diode = d["I_pv"] - d["I_0"] * (
            np.exp(np.clip((V_arr + I_arr * d["R_s"]) / (d["N_a"] * ns * vt), -80, 80)) - 1)
        residu = I_1diode - I_arr
        zone = (V_arr > voc * 0.3) & (V_arr < voc * 0.7)
        if np.any(zone):
            d["I_02"] = max(float(np.mean(np.abs(residu[zone]))), 1e-20)
        else:
            d["I_02"] = None
    else:
        d["I_02"] = None
    d["modele"] = "2-diode LLL"
    return d


def interp_tc(tc, f_legacy):
    """[FR] Coeffs thermiques interpolés à la fluence legacy f.
    [EN] Interp. thermal coeffs at legacy fluence f."""
    if not tc or not tc.get("f"):
        return {}
    ff = tc["f"]
    return {k: float(np.interp(f_legacy, ff, tc[k]))
            for k in ("dVoc", "dIsc", "dVmp", "dImp") if tc.get(k)}


def _poids_tc_yaml(c):
    """[FR] (poids, source) du coeff thermique depuis le YAML brut. [v27-S2]
    Distingue datasheet / interpolé / extrapolé / repli générique.
    Échelle : datasheet=1.0 ; interpolé/extrapolé/repli/estimé=0.3.
    [EN] (weight, source) of thermal coeff from raw YAML."""
    tc = c.get("tc")
    if not (tc and tc.get("f")):
        return 0.3, "repli générique"
    tcf = np.asarray(tc["f"], float)
    flu = np.asarray(c.get("flu") or [0.0], float)
    ti = c.get("tc_interpole")
    # extrapolation : fluence hors de la plage tc.f / fluence outside tc.f range
    if bool(np.any((flu < tcf.min() - 1e-9) | (flu > tcf.max() + 1e-9))):
        return 0.3, "extrapolé"
    # interpolation : drapeau tc_interpole présent et actif / interpolated flag set
    if ti is not None and bool(np.any(np.asarray(ti) > 0)):
        return 0.3, "interpolé"
    return (1.0, "datasheet") if c.get("tc_src") == "datasheet" else (0.3, "estimé")


def fraction_restante(dommages, param):
    """[v28-M22] Fraction restante : ∏_i (1 − D_i·w_i). [EN] Remaining fraction."""
    idx = PARAMS_ELEC.index(param)
    frac = 1.0
    for canal, D in dommages.items():
        if D is None or canal not in MATRICE_EFFET:
            continue
        w = MATRICE_EFFET[canal][idx]
        frac *= (1.0 - float(D) * w)
    return float(np.clip(frac, 0.0, 1.0))


def dommage_total(dommages, param):
    """[v28-M22] Dommage total : D_total = 1 − ∏(1 − D_i·w_i). [EN] Total damage."""
    return 1.0 - fraction_restante(dommages, param)


def _r(v, b):
    return (v / b) if (v is not None and b) else None


def _li(d, k, j):
    v = d.get(k)
    return v[j] if isinstance(v, list) and j < len(v) else None

# =============================================================================
# COLONNES / COLUMNS (76 legacy + v27 + v28-F3 + v28-F5 + v28-M17-M24)
# =============================================================================
COLONNES = [
    # --- Colonnes legacy (76) ---
    "ID Unique", "Fabricant", "Modèle", "Référence DB / Source", "Date Émission",
    "Technologie", "Nb Jonctions", "Matériau de Base", "Revêtement AR", "Type Dispositif",
    "N° Pièce", "N° Plan", "Dimensions (mm)", "Aire Cellule (cm²)", "Épaisseur (µm)",
    "Tol. Épaisseur (µm)", "Masse (mg/cm²)", "Masse (g)", "Épaisseur Contact",
    "Design Grille", "Config. Contacts", "Verre de Protection", "Matériau Interconnect.",
    "Diode Bypass", "Diode Vf @620mA (V)", "Diode Ir @2.8V (µA)",
    "Fluence (e/cm²)", "Fluence Label", "Type Radiation", "Norme Radiation",
    "Voc (mV)", "Isc (mA)", "Jsc (mA/cm²)", "Vmp (mV)", "Imp (mA)", "Jmp (mA/cm²)",
    "Pmp (mW)", "FF (%)", "η @1367 W/m² (%)", "η @1353 W/m² (%)", "η AM1.5G (%)",
    "Ratio EOL/BOL Voc", "Ratio EOL/BOL Isc", "Ratio EOL/BOL Vmp", "Ratio EOL/BOL Imp",
    "Ratio EOL/BOL Jsc", "Ratio EOL/BOL Jmp", "Ratio EOL/BOL FF", "Ratio EOL/BOL Pmp",
    "Rétention Pmp (%)",
    "ΔVoc/ΔT (mV/°C)", "ΔIsc/ΔT (mA/°C)", "ΔJsc/ΔT (µA/cm²/°C)",
    "ΔVmp/ΔT (mV/°C)", "ΔImp/ΔT (mA/°C)", "ΔJmp/ΔT (µA/cm²/°C)",
    "ΔPmp/ΔT (µW/cm²/°C)", "ΔPmp/ΔT (%/°C)", "Plage T Coefficients",
    "Absorptance Solaire", "Émittance", "Vop (mV)", "Iop avg (mA)", "Iop min (mA)",
    "Statut", "Norme Test", "Spectre", "T Référence (°C)", "Application",
    "Absorptivité", "Test Traction", "Qualification ECSS", "Niveau MRL", "Niveau TRL",
    "Références QTR", "Notes / Remarques",
    # --- v27 provenance ---
    "Component Type", "Provenance élec", "Poids TC", "Source TC",
    # --- v28-F3 radiation structurée ---
    "Radiation_particule", "Radiation_energie_MeV", "Radiation_unit",
    "Radiation_fluence_absolue", "Radiation_fluence_type", "Radiation_RDC_1MeV_e",
    # --- v28-M22 dommages ---
    "D_rad", "D_thermal", "D_age", "D_opt", "D_mech", "D_ESD", "D_impact", "D_TJ",
    "D_total_Pmp", "D_stable",
    # --- v28-M18 recuit ---
    "Recuit_actif", "Recuit_type", "Recuit_A", "Recuit_Ea_eV", "Recuit_recup_pct",
    # --- v28-M23 sous-cellules ---
    "Subcell_top_mat", "Subcell_mid_mat", "Subcell_bot_mat",
    "Subcell_top_Isc_mA", "Subcell_mid_Isc_mA", "Subcell_bot_Isc_mA",
    "Subcell_limitante",
    # --- v28-CRYO mission ---
    "Profil_mission", "Mission_irradiance_W_m2", "Mission_annealing",
    "Mission_diode_model", "Flag_LLL", "Flag_cryo",
    # --- v28-F5 diode enrichie ---
    "I_pv (mA)", "I_0 (A)", "R_s (Ω)", "N_a", "I_02 (A)", "Modele_diode",
    "R_sh (Ω)", "Erreur Ajustement (%)", "Poids Confiance Diode", "Statut Diode",
]

# =============================================================================
# CONSTRUCTION DES LIGNES / ROW BUILDING
# =============================================================================
def build_solar_rows(db):
    """[FR] 1 ligne par (cellule × fluence) + feuilles v28.
    CORRECTIF v3 : construction par row.update() (pas de TypeError doublons).
    AJOUT v27 : colonnes « Component Type » (F4), « Provenance élec » (F2),
    « Poids TC » / « Source TC » (S2).
    AJOUT v28 : colonnes radiation structurée (F3), F5 (R_sh + seuil),
    dommages (M22), recuit (M18), sous-cellules (M23), mission (CRYO).
    [EN] One row per (cell × fluence); FIX v3: row.update(); v27: provenance cols;
    v28: F3 structured radiation, F5 R_sh + threshold, damage, annealing,
    subcells, mission cols."""
    rows, therm, deg = [], [], []
    damage_rows, anneal_rows, subcell_rows, mission_rows = [], [], [], []

    for c in db.get("cellules_physique", []):
        # [v28-F3] Extraction radiation structurée / Structured radiation extraction
        rad = extraire_radiation(c)
        fluence_list = rad.get("fluence", []) or [0.0]
        n_flu = len(fluence_list)

        area = c.get("area_cm2")
        ns = c.get("N_s") or 3
        t_k = (c.get("T_ref_C") or 28) + 273.15
        poids_tc_val, src_tc = _poids_tc_yaml(c)  # [v27-S2]

        # [v28-M22] Données de dommages / Damage data
        dom = c.get("dommages", {}) or {}
        d_rad     = dom.get("rad")
        d_thermal = dom.get("thermal")
        d_age     = dom.get("age")
        d_opt     = dom.get("opt")
        d_mech    = dom.get("mech")
        d_esd     = dom.get("ESD")
        d_impact  = dom.get("impact")
        d_tj      = dom.get("TJ")
        d_stable  = c.get("d_stable_fraction")

        # [v28-M18] Données de recuit / Annealing data
        recuit = c.get("recuit") or {}
        rec_actif = recuit.get("actif", False)
        rec_type  = recuit.get("type_recuit")
        familles  = recuit.get("familles") or []
        rec_A  = familles[0].get("A") if familles else None
        rec_Ea = familles[0].get("Ea") if familles else None

        # [v28-M23] Sous-cellules / Subcells
        sc = c.get("sous_cellules") or {}
        sc_top = sc.get("top", {}) or {}
        sc_mid = sc.get("middle", {}) or {}
        sc_bot = sc.get("bottom", {}) or {}

        # [v28-CRYO] Profil mission / Mission profile
        pm_name = c.get("profil_mission") or "LEO_STANDARD"
        pm = PROFILS_MISSION.get(pm_name, PROFILS_MISSION["LEO_STANDARD"])
        flag_lll  = pm["irradiance_W_m2"] < 200.0
        flag_cryo = pm_name in ("JUICE_JUPITER", "MARS_SURFACE")

        def g0(k):
            v = c.get(k)
            return v[0] if isinstance(v, list) and v else None

        bVmp, bImp = g0("Vmp"), g0("Imp")
        bPmp = (bVmp * bImp / 1000.) if bVmp is not None and bImp is not None else None

        for i in range(n_flu):
            f_abs = fluence_list[i] if i < len(fluence_list) else 0.0
            f_legacy = f_abs / FACTEUR_LEGACY  # pour backward compatibility

            def gv(k):
                v = c.get(k)
                return v[i] if isinstance(v, list) and i < len(v) else v

            voc, isc, vmp, imp = gv("Voc"), gv("Isc"), gv("Vmp"), gv("Imp")
            jsc = isc / area if isc is not None and area else None
            jmp = imp / area if imp is not None and area else None
            pmp = vmp * imp / 1000. if vmp is not None and imp is not None else None
            if all(x is not None for x in (voc, isc, vmp, imp)) and voc and isc:
                ff = (vmp * imp) / (voc * isc) * 100
            else:
                ff = None
            e1367 = pmp / (S1367 * area) * 100 if pmp is not None and area else None
            e1353 = pmp / (S1353 * area) * 100 if pmp is not None and area else None
            tc = interp_tc(c.get("tc"), f_legacy)

            # [v28-LLL + F5] Choix du modèle diode selon irradiance mission
            if all(x is not None for x in (voc, isc, vmp, imp)):
                if flag_lll:
                    d = extraire_diode_2d_v28(voc / 1000., isc / 1000.,
                                              vmp / 1000., imp / 1000., t_k, ns)
                else:
                    d = extraire_diode_v28(voc / 1000., isc / 1000.,
                                           vmp / 1000., imp / 1000., t_k, ns)
            else:
                d = None

            # [v28-M22] D_total_Pmp / Total damage on Pmp
            dom_vals = {"rad": d_rad, "thermal": d_thermal, "age": d_age,
                        "opt": d_opt, "mech": d_mech, "ESD": d_esd,
                        "impact": d_impact, "TJ": d_tj}
            dom_valides = {k: v for k, v in dom_vals.items() if v is not None}
            d_total_pmp = dommage_total(dom_valides, "Pmp") if dom_valides else None

            # - CORRECTIF v3 : pré-remplir puis mettre à jour (pas de doublons) -
            row = {col: None for col in COLONNES}
            row.update({
                # Identification
                "ID Unique": f"{c['ref']}-{'BOL' if f_legacy == 0 else f'{f_legacy:g}E14'}",
                "Fabricant": c.get("fabricant"), "Modèle": c.get("ref"),
                "Technologie": c.get("tech"), "Nb Jonctions": ns,
                "Aire Cellule (cm²)": area, "Épaisseur (µm)": c.get("ep_um"),
                "Verre de Protection": c.get("cg_um"),
                # Radiation (legacy)
                "Fluence (e/cm²)": f_legacy * FACTEUR_LEGACY,  # backward compatible
                "Fluence Label": "BOL" if f_legacy == 0 else f"{f_legacy:g}E14",
                "Type Radiation": c.get("rad"),
                # Électrique
                "Voc (mV)": voc, "Isc (mA)": isc, "Jsc (mA/cm²)": jsc,
                "Vmp (mV)": vmp, "Imp (mA)": imp, "Jmp (mA/cm²)": jmp,
                "Pmp (mW)": pmp, "FF (%)": ff,
                "η @1367 W/m² (%)": e1367, "η @1353 W/m² (%)": e1353,
                # Ratios
                "Ratio EOL/BOL Voc": _r(voc, g0("Voc")),
                "Ratio EOL/BOL Isc": _r(isc, g0("Isc")),
                "Ratio EOL/BOL Vmp": _r(vmp, bVmp),
                "Ratio EOL/BOL Imp": _r(imp, bImp),
                "Rétention Pmp (%)": (pmp / bPmp * 100) if pmp is not None and bPmp else None,
                # Thermique
                "ΔVoc/ΔT (mV/°C)": tc.get("dVoc"),
                "ΔIsc/ΔT (mA/°C)": tc.get("dIsc"),
                "ΔVmp/ΔT (mV/°C)": tc.get("dVmp"),
                "ΔImp/ΔT (mA/°C)": tc.get("dImp"),
                # Acceptation
                "Spectre": c.get("spectre"),
                "T Référence (°C)": c.get("T_ref_C"),
                "Application": ("Terrestrial" if c.get("terrestrial") else "Space"),
                "Qualification ECSS": ("ECSS-E-ST-20-08C" if c.get("space_qualified") else None),
                "Notes / Remarques": c.get("note_fr"),
                # --- v27 provenance ---
                "Component Type": c.get("component_type", "bare_cell"),
                "Provenance élec": c.get("provenance_elec", "measured"),
                "Poids TC": poids_tc_val, "Source TC": src_tc,
                # --- v28-F3 radiation structurée ---
                "Radiation_particule": rad.get("particule"),
                "Radiation_energie_MeV": rad.get("energie_MeV"),
                "Radiation_unit": rad.get("unit"),
                "Radiation_fluence_absolue": f_abs,
                "Radiation_fluence_type": rad.get("fluence_type"),
                "Radiation_RDC_1MeV_e": rad.get("rdc"),
                # --- v28-M22 dommages ---
                "D_rad": d_rad, "D_thermal": d_thermal, "D_age": d_age,
                "D_opt": d_opt, "D_mech": d_mech, "D_ESD": d_esd,
                "D_impact": d_impact, "D_TJ": d_tj,
                "D_total_Pmp": d_total_pmp, "D_stable": d_stable,
                # --- v28-M18 recuit ---
                "Recuit_actif": rec_actif, "Recuit_type": rec_type,
                "Recuit_A": rec_A, "Recuit_Ea_eV": rec_Ea,
                # --- v28-M23 sous-cellules ---
                "Subcell_top_mat": sc_top.get("materiau"),
                "Subcell_mid_mat": sc_mid.get("materiau"),
                "Subcell_bot_mat": sc_bot.get("materiau"),
                "Subcell_top_Isc_mA": sc_top.get("Isc_mA"),
                "Subcell_mid_Isc_mA": sc_mid.get("Isc_mA"),
                "Subcell_bot_Isc_mA": sc_bot.get("Isc_mA"),
                # --- v28-CRYO mission ---
                "Profil_mission": pm_name,
                "Mission_irradiance_W_m2": pm["irradiance_W_m2"],
                "Mission_annealing": pm["annealing"],
                "Mission_diode_model": pm["diode_model"],
                "Flag_LLL": flag_lll, "Flag_cryo": flag_cryo,
                # --- v28-F5 diode enrichie ---
                "I_pv (mA)": (d["I_pv"] * 1000 if d and d.get("statut") == "actif" else None),
                "I_0 (A)": (d["I_0"] if d and d.get("statut") == "actif" else None),
                "R_s (Ω)": (d["R_s"] if d and d.get("statut") == "actif" else None),
                "N_a": (d["N_a"] if d and d.get("statut") == "actif" else None),
                "I_02 (A)": (d.get("I_02") if d and d.get("statut") == "actif" else None),
                "Modele_diode": (d.get("modele", "1-diode") if d and d.get("statut") == "actif" else None),
                "R_sh (Ω)": (d.get("R_sh") if d and d.get("statut") == "actif" else None),
                "Erreur Ajustement (%)": (d.get("erreur", 0) * 100 if d and d.get("statut") == "actif" else None),
                "Poids Confiance Diode": (d.get("poids_confiance") if d and d.get("statut") == "actif" else None),
                "Statut Diode": (d.get("statut") if d else "NON_IDENTIFIABLE"),
                # --- couleurs internes ---
                "_tech": tech_color(c.get("ref"), c.get("tech"), c.get("terrestrial")),
                "_deg": deg_color(f_legacy),
            })

            # [v28-M23] Calcul de la sous-cellule limitante
            iscs_sc = [sc_top.get("Isc_mA"), sc_mid.get("Isc_mA"), sc_bot.get("Isc_mA")]
            iscs_valid = [x for x in iscs_sc if x is not None]
            if iscs_valid:
                min_isc = min(iscs_valid)
                names = ["top", "middle", "bottom"]
                limitante = None
                for idx_n, v in enumerate(iscs_sc):
                    if v == min_isc:
                        limitante = names[idx_n]
                        break
                row["Subcell_limitante"] = limitante
            else:
                row["Subcell_limitante"] = None

            rows.append(row)

            # Ligne dégradation / Degradation row
            deg.append(dict(
                ID=c["ref"], Fabricant=c.get("fabricant"), Modèle=c.get("ref"),
                Type=c.get("component_type", "bare_cell"),
                Fluence="BOL" if f_legacy == 0 else f"{f_legacy:g}E14",
                **{"Fluence (e/cm²)": f_legacy * FACTEUR_LEGACY},
                **{"Voc EOL/BOL": _r(voc, g0("Voc")),
                   "Isc EOL/BOL": _r(isc, g0("Isc")),
                   "Vmp EOL/BOL": _r(vmp, bVmp),
                   "Imp EOL/BOL": _r(imp, bImp),
                   "Rétention Pmp (%)": (pmp / bPmp * 100) if pmp is not None and bPmp else None}))

        # Ligne thermique / Thermal row
        tcraw = c.get("tc")
        if tcraw and tcraw.get("f"):
            for j, ff in enumerate(tcraw["f"]):
                therm.append(dict(
                    ID=c["ref"], Fabricant=c.get("fabricant"),
                    Modèle=c.get("ref"),
                    Fluence="BOL" if ff == 0 else f"{ff:g}E14",
                    **{"Fluence (e/cm²)": ff * FACTEUR_LEGACY},
                    **{"ΔVoc/ΔT (mV/°C)": _li(tcraw, "dVoc", j),
                       "ΔIsc/ΔT (mA/°C)": _li(tcraw, "dIsc", j),
                       "ΔVmp/ΔT (mV/°C)": _li(tcraw, "dVmp", j),
                       "ΔImp/ΔT (mA/°C)": _li(tcraw, "dImp", j)}))

        # [v28-M22] Ligne dommages / Damage row
        if dom_valides:
            damage_rows.append(dict(
                ID=c["ref"], Fabricant=c.get("fabricant"), Modèle=c.get("ref"),
                D_rad=d_rad, D_thermal=d_thermal, D_age=d_age, D_opt=d_opt,
                D_mech=d_mech, D_ESD=d_esd, D_impact=d_impact, D_TJ=d_tj,
                D_total_Pmp=d_total_pmp, D_stable=d_stable,
                Canaux_permanents=", ".join(
                    k for k, v in dom_valides.items()
                    if STATUT_CANAL.get(k) != "PARTIALLY_REVERSIBLE"),
                Canaux_reparables=", ".join(
                    k for k, v in dom_valides.items()
                    if STATUT_CANAL.get(k) == "PARTIALLY_REVERSIBLE")))

        # [v28-M18] Ligne recuit / Annealing row
        if rec_actif:
            anneal_rows.append(dict(
                ID=c["ref"], Fabricant=c.get("fabricant"), Modèle=c.get("ref"),
                Actif=rec_actif, Type=rec_type,
                A=rec_A, Ea_eV=rec_Ea,
                Nb_familles=len(familles) if isinstance(familles, list) else 0,
                Profil_T=str(recuit.get("T_profil", ""))))

        # [v28-M23] Ligne sous-cellules / Subcell row
        if sc:
            iscs = [sc_top.get("Isc_mA"), sc_mid.get("Isc_mA"), sc_bot.get("Isc_mA")]
            iscs_valid = [x for x in iscs if x is not None]
            limitante = None
            if iscs_valid:
                min_isc = min(iscs_valid)
                names = ["top", "middle", "bottom"]
                for idx, v in enumerate(iscs):
                    if v == min_isc:
                        limitante = names[idx]
                        break
            subcell_rows.append(dict(
                ID=c["ref"], Fabricant=c.get("fabricant"), Modèle=c.get("ref"),
                Top_mat=sc_top.get("materiau"),
                Mid_mat=sc_mid.get("materiau"),
                Bot_mat=sc_bot.get("materiau"),
                Top_Eg_eV=sc_top.get("Eg_eV"),
                Mid_Eg_eV=sc_mid.get("Eg_eV"),
                Bot_Eg_eV=sc_bot.get("Eg_eV"),
                Top_Isc_mA=sc_top.get("Isc_mA"),
                Mid_Isc_mA=sc_mid.get("Isc_mA"),
                Bot_Isc_mA=sc_bot.get("Isc_mA"),
                Top_Voc_mV=sc_top.get("Voc_mV"),
                Mid_Voc_mV=sc_mid.get("Voc_mV"),
                Bot_Voc_mV=sc_bot.get("Voc_mV"),
                Limitante=limitante))

        # [v28-CRYO] Ligne mission / Mission row
        mission_rows.append(dict(
            ID=c["ref"], Fabricant=c.get("fabricant"), Modèle=c.get("ref"),
            Profil=pm_name, Distance_AU=pm["distance_AU"],
            Irradiance_W_m2=pm["irradiance_W_m2"],
            Annealing=pm["annealing"], Diode_model=pm["diode_model"],
            Damage_corr=pm["damage_corr"],
            Flag_LLL=flag_lll, Flag_cryo=flag_cryo,
            Couleur=MISSION_COLORS.get(pm_name, "FFFFFF")))

    return rows, therm, deg, damage_rows, anneal_rows, subcell_rows, mission_rows

# =============================================================================
# ÉCRITURE EXCEL / EXCEL WRITING
# =============================================================================
def write_solar_excel(db, out: Path):
    """[FR] Écrit le classeur solaire 11 feuilles + couleurs + légende.
    v27 : 7 feuilles. v28 : 11 feuilles (+ Damage_Channels, Annealing_Data,
    Subcells_3J, Mission_Profiles).
    [EN] Write 11-sheet workbook + colors + provenance legend."""
    rows, therm, deg, damage_rows, anneal_rows, subcell_rows, mission_rows = build_solar_rows(db)
    df = pd.DataFrame(rows, columns=COLONNES)

    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        df.to_excel(xw, "ALL_Data_KNIME", index=False)
        for sheet, tech in [("TJ_GaAs_30pct", "TJ"), ("QJ_GaAs_32pct", "QJ"), ("Silicon", "Si")]:
            df[df["Technologie"] == tech].to_excel(xw, sheet, index=False)
        pd.DataFrame(therm).to_excel(xw, "Thermal_Coefficients", index=False)
        pd.DataFrame(deg).to_excel(xw, "Degradation_EOL_BOL", index=False)
        # v28 feuilles / v28 sheets
        if damage_rows:
            pd.DataFrame(damage_rows).to_excel(xw, "Damage_Channels", index=False)
        if anneal_rows:
            pd.DataFrame(anneal_rows).to_excel(xw, "Annealing_Data", index=False)
        if subcell_rows:
            pd.DataFrame(subcell_rows).to_excel(xw, "Subcells_3J", index=False)
        if mission_rows:
            pd.DataFrame(mission_rows).to_excel(xw, "Mission_Profiles", index=False)

        # Légende / Legend
        leg = pd.DataFrame([
            ["COULEURS TECHNO", "", ""],
            ["Triple Junction", "Bleu clair", "D6E4F0"],
            ["3G30C (Azur)", "Bleu", "C8E6FA"],
            ["Quadruple Junction", "Vert", "D5E8D4"],
            ["3T34A", "Jaune", "FFF2CC"],
            ["Silicon", "Rose", "F8CECC"],
            ["XTJ/XTE-SF", "Violet", "E1D5E7"],
            ["ZTJ (SolAero)", "Bleu clair", "DAE8FC"],
            ["Terrestre", "Gris", "F5F5F5"],
            ["", "", ""],
            ["COULEURS DÉGRADATION", "", ""],
            ["BOL", "Blanc", "FFFFFF"],
            ["<1E14", "Jaune pâle", "FFFDE7"],
            ["<1E15", "Orange pâle", "FFF3E0"],
            ["≥1E15", "Rose", "FCE4EC"],
            ["", "", ""],
            ["COULEURS MISSION [v28]", "", ""],
            ["LEO_STANDARD", "Vert", "C6EFCE"],
            ["GEO_STANDARD", "Bleu", "BDD7EE"],
            ["JUICE_JUPITER", "Gris (cryo)", "D9D9D9"],
            ["MARS_SURFACE", "Orange", "F4B183"],
            ["", "", ""],
            ["PROVENANCE [v27]", "Poids", "Source"],
            ["datasheet mesuré", "1.0", "tc_src=datasheet, flu∈tc.f"],
            ["interpolé", "0.3", "flu dans tc.f mais non mesuré"],
            ["extrapolé", "0.3", "flu hors tc.f"],
            ["repli générique", "0.3", "pas de tc → THERMO techno"],
            ["provenance élec measured", "1.0", "valeurs publiées constructeur"],
            ["provenance élec manufacturer-derived", "0.8", "BOL × rétention (CESI)"],
            ["", "", ""],
            ["DOMMAGES [v28-M22]", "Statut", "Note"],
            ["rad", "PARTIALLY_REVERSIBLE", "Seul canal récupérable par recuit"],
            ["thermal", "PRACTICALLY_IRREVERSIBLE", "Arrhenius cumulé"],
            ["age", "PRACTICALLY_IRREVERSIBLE", "Dérive intrinsèque"],
            ["opt", "PRACTICALLY_IRREVERSIBLE", "UV/coverglass/AR"],
            ["mech", "FUNDAMENTALLY_IRREVERSIBLE", "Fissures/fatigue"],
            ["ESD", "FUNDAMENTALLY_IRREVERSIBLE", "Décharges/arcs"],
            ["impact", "FUNDAMENTALLY_IRREVERSIBLE", "MMOD/débris"],
            ["TJ", "PRACTICALLY_IRREVERSIBLE", "Jonction tunnel"],
            ["", "", ""],
            ["F3 RADIATION [v28]", "Valeurs", "Source"],
            ["RDC 3MeV p → 1MeV e", "2.66", "Rapport RT3 CDS"],
            ["RDC 9.5MeV p → 1MeV e", "9.03", "Rapport RT3 CDS"],
            ["fluence_type=experimental", "", "Mesure directe"],
            ["fluence_type=equivalent_NIEL", "", "Calcul NIEL"],
            ["fluence_type=equivalent_DDD", "", "Displacement Damage Dose"],
            ["", "", ""],
            ["F5 DIODE [v28]", "Seuil", "Note"],
            ["Rejet si erreur > 5%", "5%", "Statut = REJETÉ"],
            ["Poids confiance < 1%", "1.0", "Excellent ajustement"],
            ["Poids confiance 1-5%", "0.5", "Acceptable"],
            ["R_sh", "I-V complète", "NON_IDENTIFIABLE sans I-V"],
        ], columns=["LÉGENDE / LEGEND", "Description", "Hex/Source"])
        leg.to_excel(xw, "LEGENDE_SOURCES", index=False)

        # Couleurs / Colors
        ws = xw.sheets["ALL_Data_KNIME"]
        for r in range(2, ws.max_row + 1):
            fill = PatternFill("solid", fgColor=rows[r - 2]["_deg"])
            for col in range(1, ws.max_column + 1):
                ws.cell(r, col).fill = fill
            ws.cell(r, 1).fill = PatternFill("solid", fgColor=rows[r - 2]["_tech"])
        for col in range(1, ws.max_column + 1):
            ws.cell(1, col).font = Font(bold=True)

    n_sheets = 7 + sum(1 for x in [damage_rows, anneal_rows, subcell_rows, mission_rows] if x)
    print(f"✅ {out} : {len(df)} lignes (cellules × fluences), {n_sheets} feuilles.")

# =============================================================================
# PARTIE 3 — MENU INTERACTIF (Spyder/terminal) / INTERACTIVE MENU
# =============================================================================
BANNIERE = f"""
==========================================================================
🔄 CONVERTISSEUR EXPERT UNIFIÉ — v{__version__}
   YAML ↔ JSON ↔ Excel + EXPORT SOLAIRE + PROVENANCE (F2/F4/S2)
   + F3 (fluence structurée) + F5 (R_sh/seuil) + DOMMAGES + RECUIT
   + SOUS-CELLULES + MISSION (v28)
=========================================================================="""


def afficher_menu():
    print("" + "=" * 74)
    print(BANNIERE)
    print("=" * 74)
    print("  [1] Export solaire YAML→Excel (11 feuilles + provenance + v28)")
    print("  [2] Conversion générique (YAML/JSON/Excel)")
    print("  [3] Légende des couleurs & provenance")
    print("  [4] Profils mission disponibles [v28]")
    print("  [5] Statut F3 + F5 (fluence structurée + diode enrichie)")
    print("  [q] Quitter / Quit")
    print("-" * 74)


def run_menu_solar():
    src = input("  YAML source [solar_cells_database.yaml] : ").strip() or "solar_cells_database.yaml"
    out = input("  Excel sortie [Space_Solar_Cells_Complete_Database_gen.xlsx] : ").strip() \
          or "Space_Solar_Cells_Complete_Database_gen.xlsx"
    write_solar_excel(yaml.safe_load(Path(src).read_text(encoding="utf-8")), Path(out))


def run_menu_generic():
    src = input("  Source : ").strip()
    out = input("  Sortie : ").strip()
    fl = input("  Aplatir ? (o/n) [n] : ").strip().lower() in ("o", "y")
    DataConverter(ConversionConfig(Path(src), Path(out), flatten=fl)).convert()


def run_menu_legende():
    print("\n  COULEURS TECHNO / TECHNO COLORS :")
    for k, v in TECH_COLORS.items():
        print(f"    {k:5s} #{v}")
    print("\n  COULEURS DÉGRADATION / DEGRADATION COLORS :")
    for lab, f in [("BOL", 0), ("<1E14", 0.5), ("<1E15", 5), ("≥1E15", 50)]:
        print(f"    {lab:6s} #{deg_color(f)}")
    print("\n  COULEURS MISSION [v28] / MISSION COLORS :")
    for k, v in MISSION_COLORS.items():
        print(f"    {k:15s} #{v}")
    print("\n  PROVENANCE POIDS TC / TC WEIGHT PROVENANCE :")
    for src, w in [("datasheet", 1.0), ("interpolé", 0.3), ("extrapolé", 0.3),
                   ("repli générique", 0.3), ("estimé", 0.3)]:
        print(f"    {src:16s} poids={w:.2f}")
    print("\n  STATUT CANAUX DOMMAGE [v28-M22] / DAMAGE CHANNEL STATUS :")
    for k, v in STATUT_CANAL.items():
        print(f"    {k:8s} → {v}")


def run_menu_mission():
    """[v28-CRYO] Affiche les profils mission disponibles."""
    print("\n  PROFILS MISSION DISPONIBLES / AVAILABLE MISSION PROFILES :")
    print(f"  {'Profil':15s} {'Dist (AU)':>10s} {'Irr (W/m²)':>12s} "
          f"{'Anneal':>8s} {'Diode':>10s} {'D_corr':>8s}")
    print("  " + "-" * 70)
    for k, v in PROFILS_MISSION.items():
        print(f"  {k:15s} {v['distance_AU']:>10.2f} {v['irradiance_W_m2']:>12.1f} "
              f"{'Oui' if v['annealing'] else 'Non':>8s} {v['diode_model']:>10s} "
              f"{v['damage_corr']:>8.2f}")
    print("\n  ⚠️  JUICE_JUPITER : recuit désactivé (cryogénique), 2-diodes LLL, ×1.25 dommage")
    print("  ⚠️  MARS_SURFACE : recuit désactivé, 2-diodes LLL, ×1.10 dommage")


def run_menu_f3_f5():
    """[v28-F3+F5] Affiche le statut de la fluence structurée + diode enrichie."""
    print("\n  F3 — FLUENCE STRUCTURÉE / STRUCTURED FLUENCE")
    print("  " + "-" * 70)
    print("  Champ YAML : 'radiation' (v8, structuré)")
    print("    - particule : electron | proton | neutron | heavy_ion")
    print("    - energie_MeV : float")
    print("    - fluence : liste de valeurs absolues")
    print("    - unit : e/cm² | p/cm² | n/cm² | ion/cm²")
    print("    - fluence_type : experimental | equivalent_NIEL | equivalent_DDD")
    print("    - rdc_vers_1MeV_e : float ou null")
    print("\n  RDC MESURÉS (Rapport RT3 CDS 25.DING.ING.PCCEC) :")
    for (p, e), rdc in RDC_MESURES.items():
        print(f"    {p} {e} MeV → 1 MeV e⁻ : RDC = {rdc}")
    print("\n  BACKWARD COMPATIBLE :")
    print("    Si 'radiation' absent, conversion auto depuis flu/rad (legacy).")
    print("    flu (multiplicateur ×10^14) × 1e14 → fluence absolue")
    print("\n  COLONNES EXCEL v28-F3 :")
    cols_f3 = [c for c in COLONNES if c.startswith("Radiation_")]
    for c in cols_f3:
        print(f"    - {c}")
    print("\n  F5 — DIODE ENRICHIE / ENRICHED DIODE")
    print("  " + "-" * 70)
    print(f"  Seuil de rejet : {SEUIL_REJET:.0%}")
    print("  Si erreur d'ajustement > seuil → Statut Diode = REJETÉ")
    print("  Poids confiance : < 1% → 1.0 | 1-5% → 0.5 | > 5% → 0.0")
    print("  R_sh : NON_IDENTIFIABLE sans I-V complète")
    print("  Modèle 2-diodes : activé si irradiance mission < 200 W/m² (LLL)")
    print("\n  COLONNES EXCEL v28-F5 :")
    cols_f5 = ["I_pv (mA)", "I_0 (A)", "R_s (Ω)", "N_a", "I_02 (A)",
               "Modele_diode", "R_sh (Ω)", "Erreur Ajustement (%)",
               "Poids Confiance Diode", "Statut Diode"]
    for c in cols_f5:
        print(f"    - {c}")


def boucle_interactive():
    print(BANNIERE)
    while True:
        afficher_menu()
        ch = input("  Votre choix / Your choice : ").strip().lower()
        if ch == "q":
            print("👋 Au revoir / Goodbye.")
            break
        if ch == "1":
            run_menu_solar()
        elif ch == "2":
            run_menu_generic()
        elif ch == "3":
            run_menu_legende()
        elif ch == "4":
            run_menu_mission()
        elif ch == "5":
            run_menu_f3_f5()
        else:
            print("  Choix invalide / Invalid choice.")

# =============================================================================
# PARTIE 4 — CLI UNIFIÉ / UNIFIED CLI
# =============================================================================
def main():
    p = argparse.ArgumentParser(
        description=f"🔄 Convertisseur Expert unifié v{__version__} "
                    f"(générique + solaire + provenance + F3 + F5 + v28)")
    p.add_argument("source", nargs="?", type=Path)
    p.add_argument("output", nargs="?", type=Path)
    p.add_argument("-sf", "--source-format", choices=["yaml", "yml", "json", "xlsx", "xls"])
    p.add_argument("-of", "--output-format", choices=["yaml", "yml", "json", "xlsx", "xls"])
    p.add_argument("-i", "--indent", type=int, default=2)
    p.add_argument("-f", "--flatten", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--solar", action="store_true",
                   help="Force l'export solaire spécialisé / force specialized solar export")
    a = p.parse_args()

    # Arguments fournis → exécution directe / positional args → run directly
    if a.source and a.output:
        if not a.source.exists():
            print(f"❌ Source introuvable: {a.source}")
            sys.exit(1)
        is_solar = a.solar
        if not is_solar and a.source.suffix.lower() in (".yaml", ".yml"):
            try:
                data = yaml.safe_load(a.source.read_text(encoding="utf-8"))
                is_solar = isinstance(data, dict) and "cellules_physique" in data
            except Exception:
                is_solar = False
        if is_solar and a.output.suffix.lower() in (".xlsx", ".xls"):
            write_solar_excel(yaml.safe_load(a.source.read_text(encoding="utf-8")), a.output)
        else:
            DataConverter(ConversionConfig(
                a.source, a.output,
                FileFormat(a.source_format) if a.source_format else None,
                FileFormat(a.output_format) if a.output_format else None,
                a.indent, a.flatten, a.verbose)).convert()
    else:
        boucle_interactive()  # menu par défaut (Spyder-safe) / default menu


if __name__ == "__main__":
    main()