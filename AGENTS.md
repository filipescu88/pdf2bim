# ==============================================================================
# INSTRUKCJA OPERACYJNA AGENTA (AGENTS.md) — FORWARD PIPELINE PDF/DXF -> BIM (v2.0)
# Katalog repozytorium: /home/hermes/pdf2bim
# Plan i status kroków: /home/hermes/pdf2bim/PLAN.md
# ==============================================================================

## 1. Główne Założenia Architektoniczne
1. **JEDNO ŹRÓDŁO PRAWDY (`projects/<slug>/scene_graph.json`):**
   Żaden generator geometrii, walidator ani viewer WebXR nie ma prawa zawierać zahardkodowanych współrzędnych konkretnego budynku. Cała geometria pochodzi wyłącznie z `scene_graph.json` v2.0 walidowanego przez `pydantic`.
2. **CO NAJMNIEJ 2 DOMY TESTOWE OD PIERWSZEGO DNIA:**
   Każda zmiana schematu, walidatora i kompilatora jest weryfikowana równolegle na co najmniej dwóch odmiennych projektach:
   - `projects/dom_w_gnieznikach/` (Archon — *Dom w gnieźnikach (E)* + działka DXF Purda 585/8),
   - `projects/amor_woe1092/` (Extradom — *Amor WOE1092*).
3. **JEDEN UKŁAD WSPÓŁRZĘDNYCH (PRAWOSKRĘTNY METRYCZNY):**
   - $X$ na wschód (w prawo na rzucie), $Y$ na północ (w górę na rzucie), $Z$ w górę (wysokość).
   - Początek `(0, 0, 0)` w południowo-zachodnim narożniku obrysu budynku na poziomie posadzki parteru.
   - Zakaz stosowania transformacji `8.40 - y` w kodzie kompilatora. Transformacja do układu geodezyjnego DXF jest jawnie zapisana w `site.transform`.
4. **RDZEŃ GEOMETRII W CZYSTYM PYTHONIE NA LINUKSIE (`numpy` + `shapely` + `trimesh`):**
   - Kompilacja bryły budynku (ściany, otwory, posadzki, stropy, schody, dach, przyłącza MEP) oraz eksport do `.glb` (z `extras`) i `.usda` odbywają się lokalnie w czystym Pythonie (`<0.5 s` na CPU) i są testowane przez `pytest`.
   - **ZAKAZ LOKALNEGO HEADLESS CHROMIUM (SWIFTSHADER):** Serwer Linux nie ma GPU — nigdy nie uruchamiaj na nim przeglądarkowego WebGL (`--enable-unsafe-swiftshader`).
5. **ZDALNE GPU (`filip@192.168.0.11`, Blender 5.1) WYŁĄCZNIE DO ZADAŃ GPU / FBX:**
   - Używaj zdalnego Blendera tylko do: wypiekania lightmap Cycles, panoram stereo 360°, renderów QA oraz konwersji `.glb` -> `.fbx`.
   - Każde wywołanie zdalne musi zawierać `--python-exit-code 1`, jawny timeout, wysyłkę plików wejściowych, pobranie wynikowych plików i weryfikację, że ich `mtime` jest nowszy niż start zadania.
6. **PRACA W MAŁYCH PARTIACH I OBOWIĄZKOWA WERYFIKACJA PO KAŻDYM KROKU:**
   - Nie używaj trybu `/goal`. Dziel edycje na małe kroki.
   - Po zakończeniu każdego kroku z [`PLAN.md`](/home/hermes/pdf2bim/PLAN.md) uruchom `pytest`, sprawdź listę kontrolną `Gotowe, gdy:` i zaktualizuj status w `PLAN.md`.

## 2. Niezmienniki Geometryczne (Obowiązkowe w Testach)
1. **Ściany bez ukośnych trójkątów na podłodze:** Ściany parteru i poddasza są dzielone wokół otworów na graniastosłupy o 4-wierzchołkowej prostokątnej podstawie (góra na poddaszu opcjonalnie docięta do połaci dachu `clip_to_roof`).
2. **Zero Z-fightingu posadzek i stropów:** Posadzki pokoi są rozłącznymi wielokątami (`intersection < 0.01 m²`), stykającymi się w osiach ścian działowych, a strop (`z_bottom..z_top`) nie nakłada się z posadzką poddasza.
3. **Elewacja nad cokołem:** Okładziny elewacyjne zaczynają się powyżej rzędnej cokołu.
4. **Podbitka okapu:** Pozioma skrzynka podbitki kończy się na licu zewnętrznym ścian szczytowych, nie na nawisie dachowym.
5. **Otwory na wylot:** Okna, drzwi, okna dachowe i otwór schodowy przechodzą na wylot przez wszystkie warstwy przegrody.
6. **Pełne podstopnice schodów:** Brak bocznych trójkątnych prześwitów pod stopniami.
7. **Brak przebić dachu:** Żaden element ścian ani wyposażenia poddasza nie wystaje ponad dolną płaszczyznę połaci dachu.
