# Plan Nowej Architektury: Forward Pipeline (`pdf2bim`)

> **Status realizacji:** W trakcie (Krok 0 — Fundament)  
> **Katalog repozytorium:** `/home/hermes/pdf2bim`  
> **Zasada weryfikacji:** Po każdym kroku uruchamiane jest automatyczne sprawdzenie kryteriów `Gotowe, gdy:` (`pytest` + weryfikacja artefaktów), a status w poniższej tabeli jest aktualizowany przed przejściem do kolejnego kroku.

---

## Tabela Postępu i Weryfikacji Kroków

| Krok | Nazwa etapu | Zakres | Kryterium „Gotowe, gdy” | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Krok 0** | **Fundament** | Struktura repo `pdf2bim/`, `pyproject.toml`, `pytest`, nowy `AGENTS.md`, pobranie danych Domu 1 (`dom_w_gnieznikach`) i Domu 2 (`amor_woe1092`). | `pytest` działa i przechodzi w `<1 s`, `AGENTS.md` i `PLAN.md` opisują nowy proces i rozstrzygnięte decyzje. | ✅ Zrealizowany (`4/4 PASS`) |
| **Krok 1** | **Dane i Walidator** | Schemat `scene_graph.json` v2 (`pydantic` + JSON Schema), import DXF (`ezdxf`), generator nakładki 2D (`Overlay Preview` na PNG z PDF), pełne dane `dom_w_gnieznikach` i `amor_woe1092`, walidator topologii/metraży (PN-ISO 9836)/WZ. | Oba domy przechodzą pełną walidację (`0` błędów topologii i metrażu), a wygenerowane nakładki 2D pokrywają się z rzutami PDF. | 🔄 Następny |
| **Krok 2** | **Kompilator Architektury** | Generatory w czystym Pythonie (`numpy`/`shapely`/`trimesh`): ściany + otwory -> posadzki i stropy -> schody -> dach. Eksport `.glb` z `extras`. Testy niezmienników 3D. | Oba domy kompilują się z samego `scene_graph.json` do `.glb`, a wszystkie testy niezmienników przechodzą w `pytest`. | ⏳ Oczekuje |
| **Krok 3** | **WebXR + Mazak QA** | Viewer `web_vr/index.html` czyta kolizje, schody i drzwi z `GLB extras` / `scene_graph.json` (zero współrzędnych w JS). Mazak z `element_id` i statusami w `review/markers.json`. Zdalne GPU (bake, panoramy) z `--python-exit-code 1` i kontrolą timestampów. | Można przejść oba domy w VR bez ręcznych poprawek w JS; testy cyklu życia Mazaka i zdalnego runnera przechodzą. | ⏳ Oczekuje |
| **Krok 4** | **Eksport Unreal / Twinmotion** | Konwencja `SM_`/`M_`, pivoty, łączenie siatek wg materiału/pokoju, instancjonowanie, eksport `.glb` + `.usda` (z metadanymi) oraz zdalny `.fbx`, przyłącza `mep_sockets`. | Import obu domów do UE / Twinmotion zawiera komplet metadanych, hierarchii i `mep_sockets` bez ręcznych poprawek. | ⏳ Oczekuje |
| **Krok 5** | **Półautomatyczny Ekstraktor PDF** | Ekstrakcja skali z linii wymiarowych, kandydatów ścian (12 cm / 24–44 cm) i wielokątów pokoi (`polygonize` + etykiety z tabeli) do szkicu `scene_graph.json` sprawdzanego na nakładce 2D. | Spełniona poprzeczka `>= 90%` ścian z dokładnością `2 cm` na obu zestawach testowych PDF. | ⏳ Oczekuje |

---

## Rozstrzygnięte Decyzje Architektoniczne

1. **Drugi dom testowy (`projects/amor_woe1092/`):**
   Projekt **Extradom Amor (WOE1092)** pobrany z `C:\Users\filip\Desktop\dom2` (`extradom-amor-WOE1092-rzut-parteru-459221.pdf`, `extradom-amor-WOE1092-rzut-poddasza-459222.pdf`, `extradom-amor-WOE1092-przekroj-459223.pdf`). Pierwszy dom to **Dom w gnieźnikach (E)** (`projects/dom_w_gnieznikach/`).
2. **Rdzeń geometrii:**
   **Czysty Python (`numpy` + `shapely` + `trimesh` + `mapbox_earcut`)** na Linuksie (testowalny przez `pytest` w ułamku sekundy bez SSH). Zdalne GPU (`filip@192.168.0.11`, Blender 5.1) służy wyłącznie do zadań wymagających karty graficznej (Cycles lightmap bake, panoramy 360° stereo, rendery QA oraz konwersja do `.fbx`).
3. **Format eksportu pod Unreal Engine / Twinmotion:**
   Natywny eksport **`GLB` (glTF 2.0 z `extras`)** oraz **`USD` (`.usda`)** bezpośrednio z Pythona (przenosi hierarchię, pivoty i metadane BIM do UE5 Interchange / Twinmotion) + zdalny eksport **`.fbx`** przez Blender 5.1.

---

## Filar 1 — Schemat `scene_graph.json` v2.0
- Definicja w `pydantic` (`pdf2bim/schema/`) z eksportem do JSON Schema (`schema_version: "2.0.0"`, jednostki w metrach).
- Jeden prawoskrętny układ współrzędnych: **X na wschód, Y na północ, Z w górę**, początek `(0, 0, 0)` w południowo-zachodnim narożniku obrysu budynku (koniec z `8.40 - y`).
- Transformacja do układu geodezyjnego DXF w `site.transform`.
- Stałe ID i referencje: `opening.wall_id`, `room.level_id`, `stair.from_level_id` / `to_level_id`, `mep.room_id`.
- Ściany jako oś + grubość (`start`, `end`, `thickness`, `alignment: center|left|right`) + reguła priorytetów narożników `L`/`T`.
- Sekcje: `site`, `levels`, `walls`, `openings`, `rooms`, `slabs`, `stairs`, `roof`, `mep_sockets`, `custom_elements`, `furniture` (opcjonalne, domyślnie wyłączone).

## Filar 2 — Kompilator Geometrii (`pdf2bim/geometry/`)
- Wejście: wyłącznie `scene_graph.json`.
- Generatory: `build_walls`, `build_openings`, `build_floors_and_slabs`, `build_stairs`, `build_roof`, `build_mep_sockets`.
- Wbudowane niezmienniki geometryczne (testowane automatycznie w `pytest`):
  1. Ściany jako graniastosłupy o 4-wierzchołkowej podstawie prostokątnej (z górą opcjonalnie dociętą do połaci dachu `clip_to_roof`), zero ukośnych trójkątów na podłodze.
  2. Posadzki stykające się w osiach ścian, zero nakładania w pionie (zero Z-fightingu).
  3. Okładzina elewacji powyżej cokołu.
  4. Podbitka kończąca się na licu ścian szczytowych, nie na nawisie.
  5. Otwory przechodzące na wylot przez wszystkie warstwy ściany/dachu.
  6. Schody z pełnymi podstopnicami bez bocznych prześwitów.
  7. Elementy poddasza nie przebijają połaci dachu.

## Filar 3 — Wprowadzanie Danych i Ekstrakcja (`pdf2bim/extract/`)
- Importer DXF (`ezdxf`) do sekcji `site`.
- Generator nakładki 2D (`Overlay Preview`) nakładający wygenerowany rzut `scene_graph.json` na raster PNG strony PDF w skali.
- Półautomatyczny ekstraktor wektorów PDF (`PyMuPDF` + `shapely`).

## Filar 4 — Walidator (`pdf2bim/validate/`)
- Walidacja schematu `pydantic` i referencji ID.
- Walidacja topologii: rozłączność pokoi (`< 0.01 m²`), zawieranie w obrysie wewnętrznym, poprawne osadzenie otworów w ścianach, wolny łuk otwierania drzwi.
- Walidacja metraży: tolerancja względna `<= 5%`, na poddaszu wg **PN-ISO 9836** (`100% > 2.20 m`, `50% 1.40–2.20 m`, `0% < 1.40 m`).
- Walidacja WZ (linia zabudowy, wysokość kalenicy, kąt dachu).

## Filar 5 — WebXR + Mazak QA (`web_vr/`)
- Viewer buduje kolizje, schody i drzwi z `GLB extras` / `scene_graph.json`.
- Mazak zapisuje zgłoszenia z `element_id` i zrzutem ekranu do `projects/<slug>/review/markers.json` ze statusami `open -> needs_verification -> verified`.
