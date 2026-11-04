# ==============================================================================
# INSTRUKCJA OPERACYJNA AGENTA (AGENTS.md) — FORWARD PIPELINE PDF/DXF -> BIM (v2.0)
# Katalog repozytorium: /home/hermes/pdf2bim
# Środowisko Python: /home/hermes/pdf2bim/.venv/bin/python (.venv/bin/pytest, .venv/bin/pdf2bim)
# Plan i status kroków: /home/hermes/pdf2bim/PLAN.md
# ==============================================================================

## 1. Główne Założenia Architektoniczne
1. **JEDNO ŹRÓDŁO PRAWDY (`projects/<slug>/scene_graph.json`):**
   Żaden generator geometrii, walidator ani viewer WebXR nie ma prawa zawierać zahardkodowanych współrzędnych konkretnego budynku. Cała geometria pochodzi wyłącznie z `scene_graph.json` v2.0 walidowanego przez `pydantic`.
2. **CO NAJMNIEJ 2 DOMY TESTOWE OD PIERWSZEGO DNIA (WEKTOROWY I RASTROWY PDF):**
   Każda zmiana schematu, walidatora, nakładki 2D i kompilatora jest weryfikowana równolegle na co najmniej dwóch odmiennych projektach:
   - `projects/dom_w_gnieznikach/` (Archon — *Dom w gnieźnikach (E)*, wektorowy PDF `karta.pdf` + działka DXF `Purda 585_8 mdcp.DXF`),
   - `projects/amor_woe1092/` (Extradom — *Amor WOE1092*, rastrowy PDF `3020×4404 px` z rzutem w kształcie „L”, podcieniem wejściowym i dachem dwuspadowym `40°` + `25°` nad tarasem).
3. **JEDNOZNACZNY UKŁAD WSPÓŁRZĘDNYCH (PRAWOSKRĘTNY METRYCZNY RZUTU):**
   - $+X$ w prawo na arkuszu rzutu, $+Y$ w górę na arkuszu rzutu, $+Z$ w górę (wysokość).
   - Początek `(0, 0, 0)`: `(X=0, Y=0)` to **lewy dolny narożnik prostokąta otaczającego (AABB) zewnętrznego lica muru konstrukcyjnego parteru** (bez izolacji termicznej i tarasów), a `Z=0.00` to **poziom wykończonej posadzki parteru (`±0,00` na przekroju)**.
   - Orientacja względem północy geograficznej (strzałka `N`) oraz położenie na działce geodezyjnej DXF są zapisane wyłącznie w `site.transform` (`origin_easting`, `origin_northing`, `rotation_to_north_deg`).
4. **RDZEŃ GEOMETRII W CZYSTYM PYTHONIE NA LINUKSIE (`numpy` + `shapely` + `trimesh`):**
   - Kompilacja bryły budynku (ściany wielowarstwowe, otwory, posadzki, stropy, schody, dach, przyłącza MEP) oraz eksport do `.glb` (z `extras`) i `.usda` (ASCII OpenUSD) odbywają się lokalnie w czystym Pythonie (`<0.5 s` na CPU) i są testowane przez `.venv/bin/pytest`.
   - **ZAKAZ LOKALNEGO HEADLESS CHROMIUM (SWIFTSHADER):** Serwer Linux nie ma GPU — nigdy nie uruchamiaj na nim przeglądarkowego WebGL (`--enable-unsafe-swiftshader`).
5. **ZDALNE GPU (`filip@192.168.0.11`, Blender 5.1) WYŁĄCZNIE DO ZADAŃ GPU / FBX:**
   - Używaj zdalnego Blendera tylko do: wypiekania lightmap Cycles, panoram stereo 360°, renderów QA oraz konwersji `.glb` -> `.fbx`.
   - Każde wywołanie zdalne musi zawierać `--python-exit-code 1`, jawny timeout, wysyłkę plików wejściowych, pobranie wynikowych plików i weryfikację, że ich `mtime` jest nowszy niż start zadania.
6. **JEDNOLITE CLI (`pdf2bim`) I PRACA W MAŁYCH PARTIACH Z WERYFIKACJĄ:**
   - Wszystkie operacje są dostępne przez `.venv/bin/pdf2bim {validate|overlay|build|extract} projects/<slug>`.
   - Nie używaj trybu `/goal`. Dziel zadania na małe podkroki (`1a–1f`). Po każdym kroku uruchom `.venv/bin/pytest`, zweryfikuj kryteria `Gotowe, gdy:` i zaktualizuj status w [`PLAN.md`](/home/hermes/pdf2bim/PLAN.md).

## 2. Niezmienniki Geometryczne (Obowiązkowe w Testach)
1. **Ściany bez ukośnych trójkątów na podłodze:** Ściany parteru i poddasza są dzielone wokół otworów na graniastosłupy o 4-wierzchołkowej prostokątnej podstawie (góra na poddaszu opcjonalnie docięta analitycznie do połaci dachu `clip_to_roof`).
2. **Zero Z-fightingu posadzek i stropów:** Posadzki pokoi są rozłącznymi wielokątami (`intersection < 0.01 m²`), stykającymi się w osiach ścian działowych, a strop (`z_bottom..z_top`) nie nakłada się z posadzką poddasza.
3. **Warstwowość ścian i elewacja nad cokołem:** Warstwa wykończenia zewnętrznego (`finish_ext`) ma jawny `z_bottom_offset` powyżej cokołu.
4. **Podbitka okapu:** Pozioma skrzynka podbitki kończy się na licu zewnętrznym ścian szczytowych, nie na nawisie dachowym.
5. **Otwory na wylot przez wszystkie warstwy:** Okna, drzwi, okna dachowe i otwór schodowy przechodzą na wylot przez pełną grubość wielowarstwowej przegrody.
6. **Pełne podstopnice schodów:** Brak bocznych trójkątnych prześwitów pod stopniami.
7. **Brak przebić dachu:** Żaden element ścian ani wyposażenia poddasza nie wystaje ponad dolną płaszczyznę połaci dachu.
