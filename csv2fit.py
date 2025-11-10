
#!/usr/bin/env python3
"""
csv2fit.py — Converte um CSV simples de treino em:
  - .fit.csv (compatível com Garmin FIT SDK / FitCSVTool.jar) e
  - .zwo (Zwift/MyWhoosh)

Também pode (opcionalmente) invocar o FitCSVTool.jar para gerar o .FIT binário.

Uso:
  python csv2fit.py --in workout.csv --out meu_treino --sport cycling --zwo
  python csv2fit.py --in workout.csv --out meu_treino --sport cycling --fitcsvtool "/caminho/FitCSVTool.jar"
  python csv2fit.py --in workout.csv --out meu_treino --sport cycling --zwo --ftp 250

Formato do CSV de entrada (header obrigatório):
  workout_name,step_type,duration_type,duration_value,target_type,target_value,intensity,notes

Exemplos de valores:
- step_type: warmup, interval, recovery, cooldown, rest
- duration_type: time (segundos), distance (metros), open
- target_type: none, power, hr, cadence
- target_value:
    * power: "200", "200-250", "85%", "85%-95%" (W ou %FTP)
    * hr: "140", "140-155", "Z2", "Z2-Z3" (bpm ou zona)
    * cadence: "90", "85-95" (rpm; Zwift usa Cadence=valor único)
- intensity: active, rest

Saídas:
- <out>.fit.csv (compatível com FitCSVTool.jar)
- <out>.zwo (Zwift/MyWhoosh) se --zwo
- <out>.fit se --fitcsvtool informado (usa Java/FitCSVTool)

Observações ZWO:
- Zwift/MyWhoosh preferem potência em fração do FTP (ex.: 0.95).
- Se usar watts absolutos em power, informe --ftp para converter.
- HR não controla ERG em Zwift; adicionamos orientação em texto.
"""

import argparse
import csv
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------- MAPEAMENTOS FIT ----------
DURATION_TYPE_MAP = {
    "time": "time",
    "distance": "distance",
    "open": "open",
}

TARGET_TYPE_MAP = {
    "none": "open",
    "power": "power",
    "hr": "heart_rate",
    "heart_rate": "heart_rate",
    "cadence": "cadence",
}

INTENSITY_MAP = {
    "active": "active",
    "rest": "rest",
}

SPORT_MAP = {
    "cycling": "cycling",
    "bike": "cycling",
    "biking": "cycling",
    "running": "running",
    "run": "running",
    "strength": "resistance",
    "swim": "swimming",
}

ZONE_TEXT_TO_RANGE = {
    "z1_hr": (90, 120),
    "z2_hr": (120, 140),
    "z3_hr": (140, 155),
    "z4_hr": (155, 170),
    "z5_hr": (170, 190),

    "z1_power_pct": (50, 60),   # %FTP
    "z2_power_pct": (60, 70),
    "z3_power_pct": (70, 80),
    "z4_power_pct": (80, 90),
    "z5_power_pct": (90, 105),
}

def parse_range(text):
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None

    if "%" in s:
        parts = s.replace(" ", "").split("-")
        vals = [p.replace("%","") for p in parts]
        try:
            if len(vals) == 1:
                v = float(vals[0]); return (v, v, "pct")
            low = float(vals[0]); high = float(vals[1])
            if low > high: low, high = high, low
            return (low, high, "pct")
        except:
            pass

    zmatch = re.match(r"^\s*z(\d)\s*(?:-\s*z(\d)\s*)?$", s, re.IGNORECASE)
    if zmatch:
        z1 = int(zmatch.group(1))
        z2 = int(zmatch.group(2) or z1)
        if z1 > z2: z1, z2 = z2, z1
        return (z1, z2, "zone")

    parts = s.replace(" ", "").split("-")
    try:
        if len(parts) == 1:
            v = float(parts[0]); return (v, v, "abs")
        low = float(parts[0]); high = float(parts[1])
        if low > high: low, high = high, low
        return (low, high, "abs")
    except:
        raise ValueError(f"Valor alvo inválido: '{text}'")

def zone_to_range(for_target, zlow, zhigh):
    if for_target == "heart_rate":
        key_low = f"z{zlow}_hr"; key_high = f"z{zhigh}_hr"
    elif for_target == "power":
        key_low = f"z{zlow}_power_pct"; key_high = f"z{zhigh}_power_pct"
    else:
        raise ValueError("Zones suportadas apenas para heart_rate e power.")
    if key_low not in ZONE_TEXT_TO_RANGE or key_high not in ZONE_TEXT_TO_RANGE:
        raise ValueError(f"Zona não mapeada: {key_low} / {key_high}. Ajuste ZONE_TEXT_TO_RANGE.")
    low = ZONE_TEXT_TO_RANGE[key_low][0]
    high = ZONE_TEXT_TO_RANGE[key_high][1]
    return (low, high)

def read_steps(in_csv):
    steps = []
    with open(in_csv, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            step = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            step['_line'] = i + 1
            steps.append(step)
    return steps

def infer_workout_name(steps, fallback):
    for s in steps:
        if s.get("workout_name"):
            return s["workout_name"]
    return fallback

def fitcsv_header():
    return ["Type","Local Number","Message","Field 1","Value 1","Field 2","Value 2","Field 3","Value 3","Field 4","Value 4","Field 5","Value 5","Field 6","Value 6","Field 7","Value 7","Field 8","Value 8","Field 9","Value 9","Field 10","Value 10"]

def def_row(local_no, message):
    return ["Definition", str(local_no), message] + [""]*(len(fitcsv_header())-3)

def data_row(local_no, message, fields):
    row = ["Data", str(local_no), message]
    for (name, value) in fields:
        row += [name, str(value)]
    while len(row) < len(fitcsv_header()):
        row.append("")
    return row

def build_fitcsv_rows(workout_name, sport, steps):
    rows = []
    rows.append(def_row(0, "file_id"))
    ts = int(dt.datetime.utcnow().timestamp())
    rows.append(data_row(0, "file_id", [
        ("type","workout"),
        ("manufacturer","developer"),
        ("product","1"),
        ("time_created", ts),
        ("serial_number", ts),
    ]))

    rows.append(def_row(1, "workout"))
    rows.append(data_row(1, "workout", [
        ("sport", sport),
        ("capabilities","0"),
        ("num_valid_steps", len(steps)),
        ("wkt_name", workout_name[:20] if workout_name else "Workout"),
    ]))

    rows.append(def_row(2, "workout_step"))
    for idx, s in enumerate(steps, start=1):
        step_name = s.get("step_type","step")
        duration_type = DURATION_TYPE_MAP.get((s.get("duration_type") or "time").lower())
        if duration_type is None:
            raise ValueError(f"Linha {s.get('_line')}: duration_type inválido: '{s.get('duration_type')}'")

        duration_value = s.get("duration_value") or ""
        target_type_in = (s.get("target_type") or "none").lower()
        target_type = TARGET_TYPE_MAP.get(target_type_in)
        if target_type is None:
            raise ValueError(f"Linha {s.get('_line')}: target_type inválido: '{s.get('target_type')}'")

        intensity = INTENSITY_MAP.get((s.get("intensity") or "active").lower(), "active")
        notes = s.get("notes","")
        tval = parse_range(s.get("target_value"))
        target_low = target_high = None

        if target_type == "open":
            pass
        elif tval is None:
            pass
        else:
            low, high, mode = tval
            if mode == "zone":
                if target_type == "heart_rate":
                    low, high = zone_to_range("heart_rate", int(low), int(high))
                    target_low, target_high = int(low), int(high)
                elif target_type == "power":
                    low, high = zone_to_range("power", int(low), int(high))
                    target_low, target_high = int(low), int(high)
                else:
                    raise ValueError("Zone only supported for HR or Power.")
            elif mode == "pct":
                target_low, target_high = int(round(low)), int(round(high))
            else:
                target_low, target_high = int(round(low)), int(round(high))

        fields = [
            ("message_index", idx-1),
            ("wkt_step_name", step_name[:15]),
            ("duration_type", duration_type),
        ]

        if duration_type == "time" and duration_value:
            fields.append(("duration_value", int(float(duration_value))))
        elif duration_type == "distance" and duration_value:
            fields.append(("duration_value", int(float(duration_value))))

        fields += [("target_type", target_type), ("intensity", intensity)]

        if target_type != "open" and target_low is not None and target_high is not None:
            fields.append(("custom_target_value_low", target_low))
            fields.append(("custom_target_value_high", target_high))

        if notes:
            fields.append(("notes", notes[:20]))

        rows.append(data_row(2, "workout_step", fields))

    return rows

def write_fitcsv(out_path, rows):
    header = fitcsv_header()
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

def try_make_fit(fitcsvtool, fitcsv_path, fit_path):
    if not fitcsvtool:
        return False, "FitCSVTool não especificado."
    jar = Path(fitcsvtool)
    if not jar.exists():
        return False, f"FitCSVTool.jar não encontrado em: {jar}"
    cmd = ["java","-jar",str(jar),"-c",str(fitcsv_path),str(fit_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        ok = (res.returncode == 0)
        if not ok:
            return False, f"Falha na conversão FIT: {res.stderr or res.stdout}"
        return True, res.stdout.strip()
    except Exception as e:
        return False, f"Erro ao chamar java/FitCSVTool: {e}"

# ---------- ZWO (Zwift/MyWhoosh) EXPORT ----------
def _pct_or_abs_to_fraction(low, high, mode, ftp=None):
    if mode == "pct":
        return (low/100.0, high/100.0)
    if mode == "abs":
        if ftp and ftp > 0:
            return (low/ftp, high/ftp)
        return (None, None)
    return (None, None)

def build_zwo_xml(workout_name, sport, steps, ftp=None):
    import xml.etree.ElementTree as ET
    root = ET.Element("workout_file")
    ET.SubElement(root, "name").text = workout_name or "Workout"
    sport_map = {"cycling":"bike", "running":"run", "swimming":"bike", "resistance":"bike"}
    ET.SubElement(root, "sportType").text = sport_map.get(sport, "bike")
    ET.SubElement(root, "author").text = "csv2fit.py"

    workout_el = ET.SubElement(root, "workout")
    elapsed = 0
    textevents = ET.SubElement(root, "textevents")

    for s in steps:
        stype = (s.get("step_type") or "step").lower()
        duration_type = (s.get("duration_type") or "time").lower()
        dur = s.get("duration_value")
        seconds = 0
        if duration_type == "time" and dur:
            try:
                seconds = int(float(dur))
            except:
                seconds = 0

        target_type_in = (s.get("target_type") or "none").lower()
        notes = s.get("notes","")
        tval = parse_range(s.get("target_value"))
        t_low = t_high = None
        t_mode = None
        if tval is not None:
            t_low, t_high, t_mode = tval

        cadence = None
        if target_type_in == "cadence" and t_low is not None and t_low == t_high:
            cadence = int(round(t_low))

        tag_name = "SteadyState"
        if stype in ("warmup","wu","aquecimento"):
            tag_name = "Warmup"
        elif stype in ("cooldown","cd","volta a calma","desaquecimento"):
            tag_name = "Cooldown"
        elif target_type_in == "none":
            tag_name = "FreeRide"

        attrs = {}
        if seconds > 0:
            attrs["Duration"] = str(seconds)

        power_guidance_text = None
        hr_guidance_text = None

        if target_type_in == "power" and t_low is not None:
            zlow, zhigh = _pct_or_abs_to_fraction(t_low, t_high, t_mode, ftp=ftp)
            if zlow is not None:
                if tag_name in ("Warmup","Cooldown") and zlow is not None and zhigh is not None:
                    attrs["PowerLow"]  = f"{zlow:.3f}"
                    attrs["PowerHigh"] = f"{zhigh:.3f}"
                else:
                    if abs(zhigh - zlow) < 1e-6:
                        attrs["Power"] = f"{zlow:.3f}"
                    else:
                        attrs["PowerLow"]  = f"{zlow:.3f}"
                        attrs["PowerHigh"] = f"{zhigh:.3f}"
            else:
                tag_name = "FreeRide"
                power_guidance_text = f"Alvo potência {int(t_low)}-{int(t_high)}W (passe --ftp p/ %FTP)."

        elif target_type_in == "hr" and t_low is not None:
            hr_guidance_text = f"HR alvo: {int(t_low)}" + (f"-{int(t_high)} bpm" if t_high != t_low else " bpm")

        if cadence is not None:
            attrs["Cadence"] = str(cadence)

        step_el = ET.SubElement(workout_el, tag_name, **attrs)

        cue = s.get("notes","").strip()
        combined_text = " ".join(x for x in [cue, power_guidance_text, hr_guidance_text] if x)
        if combined_text:
            ET.SubElement(textevents, "textevent", timeoffset=str(elapsed), message=combined_text[:100])

        elapsed += seconds

    def _indent(elem, level=0):
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for e in elem:
                _indent(e, level+1)
            if not e.tail or not e.tail.strip():
                e.tail = i
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
    _indent(root)

    import xml.dom.minidom as minidom
    xml_str = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
    return pretty.decode("utf-8")

def write_zwo(out_path, xml_text):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_text)

def main():
    ap = argparse.ArgumentParser(description="Converte CSV de treino em .fit.csv (Garmin) e .zwo (Zwift/MyWhoosh), opcionalmente gerando .fit via FIT SDK")
    ap.add_argument("--in", dest="in_csv", required=True, help="CSV de entrada (treino simples)")
    ap.add_argument("--out", dest="out_base", required=True, help="Prefixo de saída (gera <out>.fit.csv / <out>.zwo e possivelmente <out>.fit)")
    ap.add_argument("--name", dest="name", default=None, help="Nome do treino (.wkt_name). Se ausente, tenta pegar da coluna workout_name")
    ap.add_argument("--sport", dest="sport", default="cycling", help="Esporte (cycling|running|swimming|strength etc.)")
    ap.add_argument("--fitcsvtool", dest="fitcsvtool", default=None, help="Caminho para FitCSVTool.jar (opcional)")
    ap.add_argument("--zwo", dest="make_zwo", action="store_true", help="Também gerar arquivo .zwo para Zwift/MyWhoosh")
    ap.add_argument("--ftp", dest="ftp", type=float, default=None, help="FTP (W). Necessário p/ converter watts absolutos em fração p/ Zwift")
    args = ap.parse_args()

    in_csv = Path(args.in_csv)
    if not in_csv.exists():
        print(f"ERRO: arquivo de entrada não encontrado: {in_csv}", file=sys.stderr)
        sys.exit(2)

    try:
        steps = read_steps(in_csv)
        if not steps:
            print("ERRO: CSV sem passos.", file=sys.stderr)
            sys.exit(2)
    except Exception as e:
        print(f"ERRO ao ler CSV: {e}", file=sys.stderr)
        sys.exit(2)

    workout_name = infer_workout_name(steps, args.name or "Workout")
    sport = SPORT_MAP.get(args.sport.lower(), "cycling")

    try:
        rows = build_fitcsv_rows(workout_name, sport, steps)
    except Exception as e:
        print(f"ERRO ao montar fit.csv: {e}", file=sys.stderr)
        sys.exit(2)

    out_csv = Path(f"{args.out_base}.fit.csv")
    write_fitcsv(out_csv, rows)
    print(f"OK: gerado {out_csv}")

    if args.make_zwo:
        try:
            zwo_text = build_zwo_xml(workout_name, sport, steps, ftp=args.ftp)
            out_zwo = Path(f"{args.out_base}.zwo")
            write_zwo(out_zwo, zwo_text)
            print(f"OK: gerado {out_zwo}")
        except Exception as e:
            print(f"ATENÇÃO: falhou ao gerar .zwo: {e}", file=sys.stderr)

    if args.fitcsvtool:
        out_fit = Path(f"{args.out_base}.fit")
        ok, msg = try_make_fit(args.fitcsvtool, out_csv, out_fit)
        if ok:
            print(f"OK: gerado {out_fit}")
        else:
            print(f"ATENÇÃO: não foi possível gerar .fit automaticamente. Motivo: {msg}")
            print("Você pode converter manualmente com:")
            print(f'  java -jar "{args.fitcsvtool}" -c "{out_csv}" "{out_fit}"')

if __name__ == "__main__":
    main()
