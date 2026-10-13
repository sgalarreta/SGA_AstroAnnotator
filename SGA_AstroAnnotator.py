"""
SGA_AstroAnnotator 1.0.0
Copyright (c) Sgalarreta 2026
SPDX-License-Identifier: GPL-3.0-or-later

Siril 1.4+ / sirilpy. Requires numpy, Pillow, PyQt6 and astropy.

Features:
- Independent title, coordinates and transparent image logo (PNG etc.).
- Live draggable preview based on Siril's auto-stretched image.
- Relative positions and reusable named profiles, stored in the user folder.
- Composites over original float32/uint16 pixels without quantizing the background.
- Nothing is written to Siril before the user clicks Apply.
- Re-checks Siril image content before applying so recent edits are not overwritten.
"""

# Script Name: SGA_AstroAnnotator
# Script Version: 1.0.0
# Siril Version: 1.4.0
# Script Category: processing
# Script Description: Live draggable title, WCS coordinates and custom logo.
# Script Author: Sgalarreta

import configparser
import json
import os
import sys
from pathlib import Path

# Siril manages a dedicated Python environment for scripts. Use its documented
# dependency manager before importing third-party GUI and imaging packages.
try:
    import sirilpy as s
except ImportError as exc:
    raise SystemExit('SGA_AstroAnnotator must be launched from Siril 1.4 or later.') from exc
s.ensure_installed('PyQt6', 'Pillow', 'astropy')

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from PyQt6.QtCore import Qt, QRectF, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QDoubleSpinBox, QSplitter, QVBoxLayout, QWidget,
    QInputDialog,
)

VERSION = "1.0.0"
COFFEE_URL = "https://buymeacoffee.com/sgalarreta"
# Configuration is stored outside the repository and is never uploaded to GitHub.
# Migrate previous installations without deleting their settings or profiles.
SETTINGS_DIR = Path.home() / ".SGA_astroannotator"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
PREVIOUS_SETTINGS_FILE = Path.home() / ".sgalarreta_astroannotator" / "settings.json"
OLD_SETTINGS_FILE = Path(__file__).with_name("annotator_settings.conf")
PREVIEW_MAX = (1420, 1000)

DEFAULTS = {
    "scientific": "", "common": "", "manual_ra": "", "manual_dec": "",
    "title_x": 5.0, "title_y": 15.0,      # Y is distance from bottom, %.
    "coords_x": 5.0, "coords_y": 6.0,    # Y is distance from bottom, %.
    "logo_x": 78.0, "logo_y": 5.0,     # Y is distance from top, %.
    "font_size": 34, "text_opacity": 100, "text_color": "#FFFFFF",
    "show_title": True, "show_coords": True,
    "logo_path": "", "show_logo": True, "logo_size": 17.0,
    "logo_opacity": 100, "always_on_top": False,
    "stack_text": False, "language": "es", "align_margin": 4.0,
}

DARK_STYLE = """
QWidget { background: #141820; color: #E7EDF6; font-size: 13px; }
QMainWindow { background: #11151D; }
QFrame#Header { background: #1A2130; border-bottom: 1px solid #303C50; }
QLabel#Title { color: #F8FBFF; font-weight: 700; font-size: 20px; }
QLabel#Muted { color: #9AA9C0; font-size: 12px; }
QLabel#Status { color: #A8BACF; font-size: 12px; }
QGroupBox { background: #1C2431; border: 1px solid #344155;
            border-radius: 10px; margin-top: 13px; padding: 16px 12px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                  color: #99B8F2; padding: 0 7px; left: 11px; }
QPushButton { background: #29364A; color: #EFF5FF; border: 1px solid #3A4B63;
              border-radius: 7px; padding: 8px 10px; font-weight: 500; }
QPushButton:hover { background: #354960; border-color: #6B88AD; }
QPushButton:pressed { background: #202C3D; }
QPushButton:disabled { color: #708095; background: #252D3B; }
QPushButton#Primary { background: #3369D5; border: 1px solid #477FEA;
                      color: white; font-weight: 700; padding: 12px; }
QPushButton#Primary:hover { background: #427DEC; }
QPushButton#Coffee { background: #D3AF64; border: 1px solid #EAC680; color: #18202A; font-weight: 700; }
QPushButton#Coffee:hover { background: #F0C872; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #101723;
    border: 1px solid #3C4B60; border-radius: 6px; padding: 6px 8px;
    selection-background-color: #487BE0; color: #F0F4FD; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6693ED; }
QComboBox QAbstractItemView { background: #1B2636; selection-background-color: #3564B0; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QSlider::groove:horizontal { height: 5px; background: #39485D; border-radius: 3px; }
QSlider::handle:horizontal { background: #6CA1FF; width: 15px; margin: -5px 0; border-radius: 7px; }
QScrollArea { border: none; background: #141820; }
QScrollBar:vertical { width: 10px; background: #141820; }
QScrollBar::handle:vertical { background: #3D4B5F; border-radius: 5px; min-height: 30px; }
QSplitter::handle { background: #273144; width: 5px; }
"""



I18N = {}
for _entry in """header|SGA_AstroAnnotator|SGA_AstroAnnotator|SGA_AstroAnnotator|SGA_AstroAnnotator|SGA_AstroAnnotator
always_top|Siempre visible|Always on top|Toujours au premier plan|Sempre in primo piano|Immer im Vordergrund
language|Idioma|Language|Langue|Lingua|Sprache
capture_group|Captura y estado|Image and status|Image et état|Immagine e stato|Bild und Status
profiles_group|Perfiles de colocación|Layout presets|Préréglages de disposition|Profili di impaginazione|Layout-Profile
text_group|Rótulos|Captions|Légendes|Didascalie|Beschriftungen
coords_group|Astrometría|Astrometry|Astrométrie|Astrometria|Astrometrie
style_group|Tipografía|Typography|Typographie|Tipografia|Typografie
logo_group|Logo personalizado|Custom logo|Logo personnalisé|Logo personalizzato|Eigenes Logo
layout_group|Alineación con el logo|Alignment with logo|Alignement avec le logo|Allineamento con il logo|Ausrichtung am Logo
coffee_group|Apoyar el proyecto|Support this project|Soutenir le projet|Sostieni il progetto|Projekt unterstützen
image_none|Imagen todavía no capturada|No image captured yet|Aucune image capturée|Nessuna immagine acquisita|Noch kein Bild erfasst
profile_choose|Seleccionar perfil guardado...|Select saved preset...|Choisir un préréglage...|Scegli un profilo salvato...|Gespeichertes Profil wählen...
load|Cargar|Load|Charger|Carica|Laden
save_as|Guardar como...|Save as...|Enregistrer sous...|Salva con nome...|Speichern unter...
delete|Eliminar|Delete|Supprimer|Elimina|Löschen
profile_help|Se guarda automáticamente la disposición. Los perfiles sirven para otras fotos.|Layout is saved automatically. Presets can be used on other photos.|La disposition est enregistrée automatiquement. Les préréglages sont réutilisables.|La disposizione si salva automaticamente. I profili si riutilizzano.|Layout wird automatisch gespeichert. Profile sind wiederverwendbar.
show_names|Mostrar nombres|Show names|Afficher les noms|Mostra nomi|Namen anzeigen
scientific|Científico|Catalog name|Nom du catalogue|Nome di catalogo|Katalogname
common|Común|Common name|Nom courant|Nome comune|Trivialname
stack|Textos apilados (un solo bloque)|Stack captions (one block)|Empiler les légendes (un seul bloc)|Impila didascalie (un blocco)|Beschriftungen stapeln (ein Block)
stack_help|Apilados: mueve nombres y coordenadas juntos. Separados: mueve cada uno.|Stacked: drag names and coordinates together. Separate: drag each one.|Empilés : déplacez noms et coordonnées ensemble. Séparés : librement.|Impilati: sposta nomi e coordinate insieme. Separati: indipendenti.|Gestapelt: Namen und Koordinaten gemeinsam ziehen. Getrennt: einzeln ziehen.
pos_title|Posición título|Caption position|Position de la légende|Posizione didascalia|Position der Beschriftung
pos_stack|Posición del bloque|Stack position|Position du bloc|Posizione del blocco|Blockposition
pos_coords|Posición AR/Dec|RA/Dec position|Position AD/Dec|Posizione AR/Dec|RA/Dekl.-Position
pos_logo|Posición logo|Logo position|Position du logo|Posizione logo|Logo-Position
text_help|Y = distancia al borde inferior. El texto crece hacia arriba.|Y = distance from bottom edge. Text grows upward.|Y = distance depuis le bord inférieur. Le texte monte.|Y = distanza dal bordo inferiore. Il testo cresce verso l’alto.|Y = Abstand vom unteren Rand. Text wächst nach oben.
show_coords|Mostrar AR / Dec|Show RA / Dec|Afficher AD / Dec|Mostra AR / Dec|RA / Dekl. anzeigen
coords_pending|Coordenadas pendientes|Coordinates not available|Coordonnées indisponibles|Coordinate non disponibili|Koordinaten nicht verfügbar
read_plate|Leer coordenadas de plate solving|Read plate-solved coordinates|Lire les coordonnées astrométriques|Leggi coordinate astrometriche|Astrometrisch gelöste Koordinaten lesen
ra_manual|AR manual|Manual RA|AD manuelle|AR manuale|RA manuell
dec_manual|Dec manual|Manual Dec|Dec manuelle|Dec manuale|Dekl. manuell
use_manual|Usar coordenadas manuales|Use manual coordinates|Utiliser les coordonnées manuelles|Usa coordinate manuali|Manuelle Koordinaten verwenden
font_size|Tamaño original|Original size|Taille originale|Dimensione originale|Originalgröße
opacity|Opacidad|Opacity|Opacité|Opacità|Deckkraft
color|Color|Color|Couleur|Colore|Farbe
show_logo|Mostrar logo|Show logo|Afficher le logo|Mostra logo|Logo anzeigen
logo_none|Ningún archivo seleccionado|No file selected|Aucun fichier sélectionné|Nessun file selezionato|Keine Datei ausgewählt
logo_choose|Elegir logo|Choose logo|Choisir un logo|Scegli logo|Logo auswählen
remove|Quitar|Remove|Retirer|Rimuovi|Entfernen
logo_width|Ancho (% imagen)|Width (% of image)|Largeur (% de l’image)|Larghezza (% immagine)|Breite (% des Bilds)
logo_opacity|Opacidad|Opacity|Opacité|Opacità|Deckkraft
logo_help|Y del logo = distancia desde arriba. PNG transparente recomendado.|Logo Y = distance from top. Transparent PNG recommended.|Y du logo = distance du haut. PNG transparent conseillé.|Y del logo = distanza dall’alto. PNG trasparente consigliato.|Logo-Y = Abstand von oben. Transparentes PNG empfohlen.
preview_title|Vista previa en directo|Live preview|Aperçu en direct|Anteprima in tempo reale|Live-Vorschau
capture|Capturar imagen de Siril|Capture image from Siril|Capturer l’image de Siril|Acquisisci immagine da Siril|Bild aus Siril übernehmen
no_preview|Abre una imagen en Siril y pulsa «Capturar imagen»|Open an image in Siril and click Capture image|Ouvrez une image dans Siril et cliquez sur Capturer|Apri un’immagine in Siril e premi Acquisisci|Bild in Siril öffnen und Bild übernehmen wählen
preview_help|Arrastra los textos o el logo para colocarlos.|Drag the captions or logo to position them.|Déplacez les légendes ou le logo à la souris.|Trascina le didascalie o il logo per posizionarli.|Beschriftungen oder Logo mit der Maus verschieben.
preview_stack|Bloque de textos seleccionado: arrastra para moverlo.|Text block selected: drag to move it.|Bloc de texte sélectionné : faites-le glisser.|Blocco di testo selezionato: trascinalo.|Textblock ausgewählt: zum Verschieben ziehen.
preview_title_selected|Título seleccionado: arrastra para moverlo.|Title selected: drag to move it.|Titre sélectionné : faites-le glisser.|Titolo selezionato: trascinalo.|Titel ausgewählt: zum Verschieben ziehen.
preview_coords_selected|Coordenadas seleccionadas: arrastra para moverlas.|Coordinates selected: drag to move them.|Coordonnées sélectionnées : faites-les glisser.|Coordinate selezionate: trascinale.|Koordinaten ausgewählt: zum Verschieben ziehen.
preview_logo_selected|Logo seleccionado: arrastra para moverlo.|Logo selected: drag to move it.|Logo sélectionné : faites-le glisser.|Logo selezionato: trascinalo.|Logo ausgewählt: zum Verschieben ziehen.
apply|APLICAR ANOTACIÓN EN SIRIL|APPLY ANNOTATION IN SIRIL|APPLIQUER LES ANNOTATIONS DANS SIRIL|APPLICA ANNOTAZIONI IN SIRIL|BESCHRIFTUNGEN IN SIRIL ANWENDEN
bottom_align|Alinear bordes inferiores|Align bottom edges|Aligner les bords inférieurs|Allinea bordi inferiori|Unterkanten ausrichten
bottom_tip|Título, coordenadas y logo compartirán la misma línea inferior.|Match the bottom edge of captions and logo.|Aligne le bas des légendes et du logo.|Allinea in basso didascalie e logo.|Beschriftungen und Logo unten ausrichten.
side_align|Igualar márgenes laterales|Match side margins|Égaliser les marges latérales|Pareggia margini laterali|Seitenabstände angleichen
side_tip|Mismo margen a la izquierda del texto y a la derecha del logo.|Same distance between text and left edge, and logo and right edge.|Même marge entre texte et bord gauche, logo et bord droit.|Stesso margine tra testo e sinistra, logo e destra.|Gleicher Abstand für Text links und Logo rechts.
center_distribute|Centrar uno y distribuir|Center one, distribute rest|Centrer un et répartir|Centra uno e distribuisci|Ein Element zentrieren, Rest verteilen
center_tip|El elegido se centra. Los demás quedan a los lados, alineados abajo.|Center selected element. Place others left/right, bottoms aligned.|Centre l’élément choisi. Les autres vont sur les côtés, bas alignés.|Centra l’elemento scelto; gli altri ai lati, allineati in basso.|Ausgewähltes Element zentrieren, andere seitlich und unten ausrichten.
center_item|Elemento central|Center element|Élément central|Elemento centrale|Mittleres Element
center_title|Nombres|Names|Noms|Nomi|Namen
center_coords|Coordenadas|Coordinates|Coordonnées|Coordinate|Koordinaten
center_logo|Logo|Logo|Logo|Logo|Logo
center_block|Textos apilados|Stacked captions|Légendes empilées|Didascalie impilate|Gestapelte Beschriftungen
margin|Margen lateral|Side margin|Marge latérale|Margine laterale|Seitenabstand
align_help|Estos botones alinean los textos con el logo, no solo entre sí.|These buttons align captions relative to the logo, not just to each other.|Ces boutons alignent les légendes par rapport au logo.|Questi pulsanti allineano le didascalie rispetto al logo.|Diese Schaltflächen richten die Texte am Logo aus.
coffee_button|Buy Me a Coffee|Buy Me a Coffee|Buy Me a Coffee|Buy Me a Coffee|Buy Me a Coffee
coffee_open_failed|No se pudo abrir el navegador.|Could not open your web browser.|Impossible d’ouvrir le navigateur.|Impossibile aprire il browser.|Der Browser konnte nicht geöffnet werden.
logo_error|No se puede abrir el logo: {error}|Cannot open logo: {error}|Impossible d’ouvrir le logo : {error}|Impossibile aprire il logo: {error}|Logo kann nicht geöffnet werden: {error}
image_captured|Imagen capturada. La previsualización no modifica Siril.|Image captured. Preview does not modify Siril.|Image capturée. L’aperçu ne modifie pas Siril.|Immagine acquisita. L’anteprima non modifica Siril.|Bild übernommen. Vorschau verändert Siril nicht.
image_capture_error|No se pudo capturar la imagen: {error}|Could not capture image: {error}|Capture de l’image impossible : {error}|Impossibile acquisire l’immagine: {error}|Bild konnte nicht übernommen werden: {error}
image_unavailable|No hay imagen disponible|No image available|Aucune image disponible|Nessuna immagine disponibile|Kein Bild verfügbar
coords_reset|Coordenadas pendientes para esta imagen|Coordinates pending for this image|Coordonnées en attente pour cette image|Coordinate da leggere per questa immagine|Koordinaten für dieses Bild fehlen
coords_read|Coordenadas de plate solving actualizadas.|Plate-solved coordinates updated.|Coordonnées astrométriques mises à jour.|Coordinate astrometriche aggiornate.|Astrometrische Koordinaten aktualisiert.
coords_error|Error de plate solving: {error}|Plate-solving error: {error}|Erreur de résolution astrométrique : {error}|Errore di risoluzione astrometrica: {error}|Fehler bei der astrometrischen Lösung: {error}
coords_no_wcs|La imagen actual no contiene una solución astrométrica WCS.|Current image has no WCS astrometric solution.|L’image actuelle n’a pas de solution astrométrique WCS.|L’immagine corrente non contiene una soluzione astrometrica WCS.|Aktuelles Bild enthält keine astrometrische WCS-Lösung.
coords_invalid_wcs|La cabecera no contiene WCS celeste.|No celestial WCS in header.|L’en-tête ne contient pas de WCS céleste.|L’intestazione non contiene WCS celeste.|Kein Himmels-WCS im Header.
manual_both|Introduce AR y Dec.|Enter both RA and Dec.|Saisissez AD et Dec.|Inserisci AR e Dec.|RA und Dekl. eingeben.
manual_applied|Coordenadas manuales aplicadas.|Manual coordinates applied.|Coordonnées manuelles appliquées.|Coordinate manuali applicate.|Manuelle Koordinaten übernommen.
preview_error|No se pudo actualizar la vista previa: {error}|Could not update preview: {error}|Mise à jour de l’aperçu impossible : {error}|Impossibile aggiornare l’anteprima: {error}|Vorschau konnte nicht aktualisiert werden: {error}
need_image|Captura una imagen primero.|Capture an image first.|Capturez d’abord une image.|Acquisisci prima un’immagine.|Zuerst ein Bild übernehmen.
need_logo|Selecciona y activa un logo para utilizar la alineación.|Select and enable a logo to use alignment.|Sélectionnez et activez un logo pour l’alignement.|Seleziona e abilita un logo per l’allineamento.|Logo auswählen und aktivieren, um auszurichten.
need_text|Activa al menos un rótulo con contenido.|Enable at least one caption with text.|Activez au moins une légende non vide.|Attiva almeno una didascalia con testo.|Mindestens eine ausgefüllte Beschriftung aktivieren.
fit_error|Los elementos no caben sin superponerse. Reduce el tamaño o el margen.|Items will not fit without overlap. Reduce sizes or side margin.|Les éléments se chevauchent. Réduisez leur taille ou la marge.|Gli elementi si sovrappongono. Riduci dimensioni o margine.|Elemente überlappen. Größe oder Seitenabstand reduzieren.
overlap_warning|Hay elementos superpuestos o fuera de la imagen. Muévelos o cambia la disposición.|Elements overlap or lie outside the image. Move them or change layout.|Des éléments se chevauchent ou sortent de l’image. Réorganisez-les.|Gli elementi si sovrappongono o escono dall’immagine. Riposizionali.|Elemente überlappen oder liegen außerhalb des Bilds. Bitte verschieben.
position_applied|Alineación aplicada.|Alignment applied.|Alignement appliqué.|Allineamento applicato.|Ausrichtung angewendet.
profile_saved|Perfil «{name}» guardado.|Preset “{name}” saved.|Préréglage « {name} » enregistré.|Profilo «{name}» salvato.|Profil „{name}“ gespeichert.
profile_loaded|Perfil «{name}» cargado.|Preset “{name}” loaded.|Préréglage « {name} » chargé.|Profilo «{name}» caricato.|Profil „{name}“ geladen.
save_profile|Guardar perfil|Save preset|Enregistrer le préréglage|Salva profilo|Profil speichern
name_profile|Nombre del perfil:|Preset name:|Nom du préréglage :|Nome profilo:|Profilname:
overwrite_profile|Sobrescribir perfil|Overwrite preset|Écraser le préréglage|Sovrascrivi profilo|Profil überschreiben
confirm_overwrite|¿Sobrescribir «{name}»?|Overwrite “{name}”?|Écraser « {name} » ?|Sovrascrivere «{name}»?|„{name}“ überschreiben?
delete_profile|Eliminar perfil|Delete preset|Supprimer le préréglage|Elimina profilo|Profil löschen
confirm_delete|¿Eliminar «{name}»?|Delete “{name}”?|Supprimer « {name} » ?|Eliminare «{name}»?|„{name}“ löschen?
text_color|Color del texto|Text color|Couleur du texte|Colore del testo|Textfarbe
select_logo|Seleccionar logo|Select logo|Choisir un logo|Seleziona logo|Logo auswählen
apply_success|Anotación aplicada a Siril. Guarda la imagen desde Siril cuando quieras.|Annotation applied in Siril. Save the image from Siril.|Annotation appliquée dans Siril. Enregistrez l’image depuis Siril.|Annotazione applicata in Siril. Salva l’immagine da Siril.|Beschriftung in Siril angewendet. Bild in Siril speichern.
apply_error|No se pudo aplicar la anotación|Could not apply annotation|Annotation non appliquée|Impossibile applicare annotazione|Beschriftung konnte nicht angewendet werden
apply_error_detail|Error al aplicar: {error}|Error applying: {error}|Erreur à l’application : {error}|Errore nell’applicazione: {error}|Fehler beim Anwenden: {error}
image_changed|La imagen abierta ha cambiado. Captúrala de nuevo.|Open image has changed. Capture it again.|L’image ouverte a changé. Capturez-la à nouveau.|L’immagine aperta è cambiata. Acquisiscila di nuovo.|Das geöffnete Bild hat sich geändert. Bitte erneut übernehmen.
settings_error|No se pudo guardar la configuración: {error}|Could not save settings: {error}|Enregistrement des réglages impossible : {error}|Impossibile salvare impostazioni: {error}|Einstellungen konnten nicht gespeichert werden: {error}
image_pixels_changed|La imagen en Siril ha cambiado desde la última captura. Pulsa Capturar imagen para actualizar la vista previa antes de aplicar.|The image in Siril has changed since capture. Capture the image again before applying.|L’image dans Siril a changé depuis la capture. Capturez-la à nouveau avant d’appliquer.|L’immagine in Siril è cambiata dopo l’acquisizione. Acquisiscila di nuovo prima di applicare.|Das Bild in Siril wurde seit der Aufnahme verändert. Bitte vor dem Anwenden erneut erfassen.
apply_rejected|Siril no ha aceptado la imagen anotada.|Siril did not accept the annotated image.|Siril n’a pas accepté l’image annotée.|Siril non ha accettato l’immagine annotata.|Siril hat das beschriftete Bild nicht angenommen.""".splitlines():
    _key, *_values = _entry.split("|", 5)
    if len(_values) != 5:
        raise RuntimeError(f"Invalid translation {_key}")
    I18N[_key] = dict(zip(("es", "en", "fr", "it", "de"), _values))

COORD_PREFIXES = {"es": ("AR", "Dec"), "en": ("RA", "Dec"),
                  "fr": ("AD", "Dec"), "it": ("AR", "Dec"),
                  "de": ("RA", "Dekl.")}

def tr(lang, key, **fmt):
    template = I18N.get(key, {}).get(lang) or I18N.get(key, {}).get("es", key)
    return template.format(**fmt) if fmt else template


def clamp(v, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, float(v)))


def normalize_pixels(data):
    """Accept Siril CHW or HW and return an owned CHW array."""
    arr = np.asarray(data)
    if arr.ndim == 2:
        arr = arr[None, ...]
    if arr.ndim != 3 or arr.shape[0] not in (1, 3):
        raise ValueError(f"Formato de imagen incompatible: {arr.shape}. Se espera CHW (1 o 3 canales).")
    if arr.dtype not in (np.dtype("float32"), np.dtype("uint16")):
        # Preview data can also be uint8; original Siril data should be 16bit/float.
        if arr.dtype != np.dtype("uint8"):
            raise ValueError(f"Tipo de píxel incompatible: {arr.dtype}")
    return np.ascontiguousarray(arr)


def rgb8_from_siril(data):
    """Convert Siril's bottom-up CHW pixels to an upright RGB PIL image."""
    arr = normalize_pixels(data)
    display = np.flip(arr.transpose(1, 2, 0), axis=0)
    if display.dtype == np.uint8:
        result = display
    elif display.dtype == np.uint16:
        result = np.rint(display.astype(np.float32) * (255.0 / 65535.0)).clip(0, 255).astype(np.uint8)
    else:
        result = np.rint(np.nan_to_num(display, nan=0.0, posinf=1.0, neginf=0.0) * 255).clip(0, 255).astype(np.uint8)
    if result.shape[2] == 1:
        return Image.fromarray(result[:, :, 0], "L").convert("RGB")
    return Image.fromarray(np.ascontiguousarray(result), "RGB")


def font_for_size(size):
    """Prefer the font used in the original script, then macOS/system alternatives."""
    candidates = [
        "/Library/Fonts/Nasalization Rg.otf",
        str(Path.home() / "Library/Fonts/Nasalization Rg.otf"),
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, max(2, int(round(size))))
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def calc_text_lines(state, item, coords):
    if item == "title":
        if not state.get("show_title", True):
            return []
        return [x.strip() for x in (state.get("scientific", ""), state.get("common", "")) if x.strip()]
    if item == "coords":
        if not state.get("show_coords", True) or not coords:
            return []
        ra, dec = COORD_PREFIXES.get(state.get("language", "es"), COORD_PREFIXES["es"])
        return [f"{ra}: {coords[0]}", f"{dec}: {coords[1]}"]
    return []


def prepare_logo(path):
    """Return an RGBA copy with orientation already corrected."""
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGBA")


def text_geometry(size, state, coords=None, font_scale=1.0):
    """Text geometries; stacked captions use title_x/title_y as group left/bottom."""
    w, h = map(int, size)
    fontsize = max(2, round(float(state.get("font_size", 34)) * font_scale))
    font = font_for_size(fontsize)
    gap = max(2, round(fontsize * 0.27))
    dr = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    blocks = {}
    for key in ("title", "coords"):
        lines = calc_text_lines(state, key, coords)
        if not lines:
            continue
        metrics = [dr.textbbox((0, 0), line, font=font, anchor="lt") for line in lines]
        widths = [max(1, b[2] - b[0]) for b in metrics]
        heights = [max(1, b[3] - b[1]) for b in metrics]
        bw = max(widths)
        bh = sum(heights) + gap * (len(lines) - 1)
        x = round(clamp(state.get(key + "_x", 5)) * w / 100)
        bottom = round((1 - clamp(state.get(key + "_y", 10)) / 100) * h)
        blocks[key] = {"lines": lines, "heights": heights,
                       "box": (x, bottom - bh, x + bw, bottom), "gap": gap}
    if state.get("stack_text", False) and blocks:
        group_x = round(clamp(state.get("title_x", 5)) * w / 100)
        group_bottom = round((1 - clamp(state.get("title_y", 10)) / 100) * h)
        inter_gap = gap if "title" in blocks and "coords" in blocks else 0
        cursor = group_bottom
        for key in ("coords", "title"):
            if key in blocks:
                b = blocks[key]["box"]
                bw, bh = b[2]-b[0], b[3]-b[1]
                cursor -= bh
                blocks[key]["box"] = (group_x, cursor, group_x+bw, cursor+bh)
                cursor -= inter_gap
    return font, blocks


def logo_geometry(size, state, logo):
    if logo is None or not state.get("show_logo", True):
        return None
    w, h = map(int, size)
    tw = max(1, round(w * clamp(state.get("logo_size", 17), 0.5, 100) / 100))
    th = max(1, round(tw * logo.height / max(1, logo.width)))
    if th > h:
        th = h
        tw = max(1, round(h * logo.width / max(1, logo.height)))
    x = round(clamp(state.get("logo_x", 78)) * w / 100)
    y = round(clamp(state.get("logo_y", 5)) * h / 100)
    return (x, y, x+tw, y+th)


def layout_boxes(size, state, coords=None, logo=None):
    _, blocks = text_geometry(size, state, coords)
    result = {k: v["box"] for k, v in blocks.items()}
    if state.get("stack_text", False) and blocks:
        rects = [b["box"] for b in blocks.values()]
        result["text_stack"] = (min(b[0] for b in rects), min(b[1] for b in rects),
                                max(b[2] for b in rects), max(b[3] for b in rects))
    lbox = logo_geometry(size, state, logo)
    if lbox is not None:
        result["logo"] = lbox
    return result


def layout_issues(size, state, coords=None, logo=None):
    """Reject accidental overlap/clipping, including the logo, at final resolution."""
    w, h = size
    boxes = layout_boxes(size, state, coords, logo)
    keys = (["text_stack"] if "text_stack" in boxes else [k for k in ("title", "coords") if k in boxes])
    if "logo" in boxes:
        keys.append("logo")
    if any(boxes[k][0] < 0 or boxes[k][1] < 0 or boxes[k][2] > w or boxes[k][3] > h for k in keys):
        return True
    return any(rectangles_touch(boxes[a], boxes[b], 0)
               for i, a in enumerate(keys) for b in keys[i+1:])


def rectangles_touch(a, b, gap=0):
    """Test rectangles with an additional minimum separation in pixels."""
    return (a[0] < b[2] + gap and a[2] + gap > b[0] and
            a[1] < b[3] + gap and a[3] + gap > b[1])


def resolve_text_overlap(size, state, coords, preserve="coords"):
    """
    Return a corrected state, leaving the preferred text block untouched.
    Prefer an unclipped vertical placement, then a horizontal one. The widget
    coordinates remain truthful because the caller copies the correction back
    into its spin boxes. If there is no collision, nothing changes.
    """
    w, h = map(int, size)
    if w <= 0 or h <= 0:
        return dict(state)
    _, blocks = text_geometry((w, h), state, coords)
    if not all(k in blocks for k in ("title", "coords")):
        return dict(state)
    preserve = preserve if preserve in blocks else "coords"
    moving = "coords" if preserve == "title" else "title"
    fixed = blocks[preserve]["box"]
    old = blocks[moving]["box"]
    margin = max(5, round(float(state.get("font_size", 34)) * 0.30))
    if not rectangles_touch(old, fixed, margin):
        return dict(state)

    mw, mh = old[2] - old[0], old[3] - old[1]
    # Order matters: a title should normally go above the coordinates.
    above = (old[0], fixed[1] - margin - mh)
    below = (old[0], fixed[3] + margin)
    left = (fixed[0] - margin - mw, old[1])
    right = (fixed[2] + margin, old[1])
    candidates = ((above, below, right, left) if moving == "title" else
                  (below, above, right, left))
    valid = []
    for order, (x, y) in enumerate(candidates):
        if 0 <= x <= w - mw and 0 <= y <= h - mh:
            rect = (x, y, x + mw, y + mh)
            if not rectangles_touch(rect, fixed, margin - 1):
                valid.append((order, x, y))
    if not valid:
        # Impossible to accommodate both within the image at current font size.
        return dict(state)

    # Prioritize natural reading order (vertical first), then the smaller move.
    _, x, y = min(valid, key=lambda item: (item[0],
                        abs(item[1] - old[0]) + abs(item[2] - old[1])))
    corrected = dict(state)
    # Positions are later rounded to the 0.1%-precision spin boxes.
    corrected[moving + "_x"] = clamp(x / w * 100)
    corrected[moving + "_y"] = clamp((1.0 - (y + mh) / h) * 100)
    return corrected


def paint_annotations(size, state, coords=None, logo=None, font_scale=1.0):
    """Render transparent layer with matching preview/output geometry."""
    w, h = map(int, size)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    boxes = {}
    font, blocks = text_geometry(size, state, coords, font_scale=font_scale)
    color = QColor(str(state.get("text_color", "#FFFFFF")))
    if not color.isValid():
        color = QColor("#FFFFFF")
    fill = (color.red(), color.green(), color.blue(),
            round(clamp(state.get("text_opacity", 100)) * 2.55))
    for key, block in blocks.items():
        x, y, _x2, _y2 = block["box"]
        cy = y
        for line, height in zip(block["lines"], block["heights"]):
            dr.text((x, cy), line, font=font, fill=fill, anchor="lt")
            cy += height + block["gap"]
        boxes[key] = block["box"]
    if state.get("stack_text", False) and blocks:
        bb = list(boxes.values())
        boxes["text_stack"] = (min(b[0] for b in bb), min(b[1] for b in bb),
                               max(b[2] for b in bb), max(b[3] for b in bb))
    lbox = logo_geometry(size, state, logo)
    if lbox:
        x, y, x2, y2 = lbox
        mark = logo.resize((x2-x, y2-y), Image.Resampling.LANCZOS)
        opacity = clamp(state.get("logo_opacity", 100)) / 100
        if opacity < 1:
            mark.putalpha(mark.getchannel("A").point(lambda a: round(a * opacity)))
        layer.alpha_composite(mark, (x, y))
        boxes["logo"] = lbox
    return layer, boxes


def blend_overlay_into_siril(original, overlay):
    """Only blend inside the overlay rectangle. Untouched pixels retain exact values."""
    inp = normalize_pixels(original)
    if inp.dtype not in (np.float32, np.uint16):
        raise ValueError("Siril solo acepta float32 o uint16 como imagen de salida.")
    if overlay.size != (inp.shape[2], inp.shape[1]):
        raise ValueError("La capa y la imagen no tienen las mismas dimensiones.")
    roi = overlay.getbbox()
    result = inp.copy()
    if roi is None:
        return result
    x1, y1, x2, y2 = roi
    src = np.array(overlay.crop(roi), dtype=np.uint8)[::-1, :, :]
    alpha = src[..., 3].astype(np.float32)[..., None] / 255.0
    if not np.any(alpha):
        return result
    # The image in Siril has its origin at the bottom; Pillow at the top.
    original_window = result[:, inp.shape[1] - y2: inp.shape[1] - y1, x1:x2]
    base = original_window.transpose(1, 2, 0).astype(np.float32)
    ink = src[..., :3].astype(np.float32) / 255.0
    if base.shape[2] == 1:
        ink = np.dot(ink, np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))[..., None]
    if inp.dtype == np.uint16:
        ink *= 65535.0
    mixed = base * (1.0 - alpha) + ink * alpha
    if inp.dtype == np.uint16:
        mixed = np.rint(mixed).clip(0, 65535).astype(np.uint16)
    else:
        mixed = mixed.astype(np.float32)
    original_window[...] = mixed.transpose(2, 0, 1)
    return np.ascontiguousarray(result)


def load_data():
    storage = {"current": dict(DEFAULTS), "profiles": {}}
    # Prefer the new configuration, then the previous public name.
    # Migration is completed on the next automatic save.
    source = SETTINGS_FILE if SETTINGS_FILE.is_file() else PREVIOUS_SETTINGS_FILE
    if source.is_file():
        try:
            obj = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                current = obj.get("current", {})
                if isinstance(current, dict):
                    storage["current"].update({k: v for k, v in current.items() if k in DEFAULTS})
                profiles = obj.get("profiles", {})
                if isinstance(profiles, dict):
                    storage["profiles"] = {k: v for k, v in profiles.items() if isinstance(k, str) and isinstance(v, dict)}
        except (OSError, ValueError, TypeError):
            pass
    elif OLD_SETTINGS_FILE.is_file():
        # One-time compatible migration of layout from v1.4.
        cfg = configparser.ConfigParser()
        try:
            cfg.read(OLD_SETTINGS_FILE)
            sec = cfg["Settings"]
            storage["current"].update({
                "title_x": float(sec.get("pos_x", "5")),
                "title_y": float(sec.get("pos_y", "10")),
                "coords_x": float(sec.get("pos_x", "5")),
                "coords_y": max(0.0, float(sec.get("pos_y", "10")) - 7),
                "font_size": sec.getint("font_size", 30),
                "text_opacity": sec.getint("opacity", 100),
                "text_color": "#{:02X}{:02X}{:02X}".format(
                    sec.getint("color_r", 255), sec.getint("color_g", 255), sec.getint("color_b", 255)),
                "always_on_top": bool(sec.getint("always_on_top", 0)),
            })
        except (OSError, KeyError, ValueError, TypeError):
            pass
    return storage


def save_data(storage):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(storage, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, SETTINGS_FILE)


class PreviewCanvas(QWidget):
    """Fitted interactive canvas; displays the exact composited preview buffer."""
    positionChanged = pyqtSignal(str, float, float)
    selectedChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 300)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._pixmap = None
        self._boxes = {}
        self._selected = ""
        self._dragging = False
        self._last = None
        self.language = "es"
        self.setToolTip(tr(self.language, "preview_help"))

    def set_preview(self, img, boxes):
        img = img.convert("RGB")
        pixels = np.ascontiguousarray(np.asarray(img))
        qim = QImage(pixels.data, img.width, img.height, 3 * img.width, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qim.copy())
        self._boxes = boxes
        self.update()

    def draw_rect(self):
        if self._pixmap is None:
            return QRectF()
        iw, ih = self._pixmap.width(), self._pixmap.height()
        scale = min(self.width() / iw, self.height() / ih)
        rw, rh = iw * scale, ih * scale
        return QRectF((self.width() - rw) / 2, (self.height() - rh) / 2, rw, rh)

    def _from_canvas(self, pos):
        r = self.draw_rect()
        if not r.isValid() or r.width() <= 0:
            return None
        return ((pos.x() - r.left()) * self._pixmap.width() / r.width(),
                (pos.y() - r.top()) * self._pixmap.height() / r.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0C121B"))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._pixmap is None:
            painter.setPen(QColor("#7C8FA8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             tr(self.language, "no_preview"))
            return
        r = self.draw_rect()
        painter.drawPixmap(r, self._pixmap, QRectF(self._pixmap.rect()))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        sx = r.width() / self._pixmap.width()
        sy = r.height() / self._pixmap.height()
        for item, bbox in self._boxes.items():
            if "text_stack" in self._boxes and item in ("title", "coords"):
                continue
            is_selected = self._selected == item
            stroke = QColor("#81B6FF" if is_selected else "#637E9F")
            pen = QPen(stroke, 2 if is_selected else 1)
            pen.setStyle(Qt.PenStyle.SolidLine if is_selected else Qt.PenStyle.DashLine)
            painter.setPen(pen)
            x1, y1, x2, y2 = bbox
            rr = QRectF(r.left() + x1 * sx, r.top() + y1 * sy,
                        max(2, (x2 - x1) * sx), max(2, (y2 - y1) * sy))
            painter.drawRect(rr)

    def hit_test(self, pos):
        pt = self._from_canvas(pos)
        if pt is None:
            return ""
        x, y = pt
        # Logo is in front, then coordinates, title.
        for key in (("logo", "text_stack") if "text_stack" in self._boxes else
                    ("logo", "coords", "title")):
            b = self._boxes.get(key)
            if b and b[0] - 7 <= x <= b[2] + 7 and b[1] - 7 <= y <= b[3] + 7:
                return key
        return ""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.hit_test(event.position())
            self._selected = item
            self._dragging = bool(item)
            self._last = self._from_canvas(event.position()) if item else None
            self.setCursor(Qt.CursorShape.ClosedHandCursor if item else Qt.CursorShape.ArrowCursor)
            self.selectedChanged.emit(item)
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pt = self._from_canvas(event.position())
        if self._dragging and pt and self._last and self._selected and self._selected in self._boxes:
            dx = pt[0] - self._last[0]
            dy = pt[1] - self._last[1]
            self._last = pt
            self.positionChanged.emit(self._selected, dx / self._pixmap.width() * 100,
                                      dy / self._pixmap.height() * 100)
        elif not self._dragging:
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.hit_test(event.position())
                           else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._last = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)


class AstroAnnotator(QMainWindow):
    def __init__(self, siril):
        super().__init__()
        self.siril = siril
        self.storage = load_data()
        self.state = {key: self.storage['current'].get(key, default)
                      for key, default in DEFAULTS.items()}
        if self.state.get('language') not in ('es', 'en', 'fr', 'it', 'de'):
            self.state['language'] = 'es'
        self.coords = None
        self.clean_snapshot = None
        self.capture_filename = None
        self.preview_base = None
        self.original_size = (1, 1)
        self.logo = None
        self._updating = False
        self.groups, self.labels, self.buttons, self.hints = {}, {}, {}, {}
        self.setWindowTitle('SGA_AstroAnnotator  v' + VERSION)
        self.resize(1350, 835)
        self.setMinimumSize(1030, 625)
        self.setStyleSheet(DARK_STYLE)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.render_preview)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.persist)
        self._make_ui()
        self._restore_state()
        QTimer.singleShot(0, self.capture_base_image)

    def t(self, key, **fmt):
        return tr(self.state.get('language', 'es'), key, **fmt)

    def _group(self, key):
        group = QGroupBox()
        self.groups[key] = group
        form = QFormLayout(group)
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.controls.addWidget(group)
        return form

    def _row(self, form, key, widget):
        label = QLabel()
        self.labels[key] = label
        form.addRow(label, widget)
        return label

    def _hint(self, form, key):
        hint = QLabel()
        hint.setObjectName('Muted')
        hint.setWordWrap(True)
        form.addRow(hint)
        self.hints[key] = hint
        return hint

    def _button(self, key, callback=None):
        btn = QPushButton()
        self.buttons[key] = btn
        if callback is not None:
            btn.clicked.connect(callback)
        return btn

    def _connect(self, widget):
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self.changed)
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(self.changed)
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(self.changed)

    def _spin(self, minimum, maximum, decimals=1, suffix=' %'):
        widget = QDoubleSpinBox() if decimals else QSpinBox()
        widget.setRange(minimum, maximum)
        if decimals:
            widget.setDecimals(decimals)
            widget.setSingleStep(0.5)
        widget.setSuffix(suffix)
        self._connect(widget)
        return widget

    def _positions(self, form, key):
        row = QHBoxLayout()
        x, y = self._spin(0, 100), self._spin(0, 100)
        row.addWidget(QLabel('X'))
        row.addWidget(x)
        row.addWidget(QLabel('Y'))
        row.addWidget(y)
        self._row(form, key, row)
        return x, y

    def _make_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName('Header')
        hbar = QHBoxLayout(header)
        hbar.setContentsMargins(22, 13, 22, 13)
        tit = QLabel('SGA_AstroAnnotator')
        tit.setObjectName('Title')
        hbar.addWidget(tit)
        version = QLabel('v' + VERSION)
        version.setObjectName('Muted')
        hbar.addWidget(version)
        hbar.addStretch()
        self.lang_label = QLabel()
        self.lang_label.setObjectName('Muted')
        hbar.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        for code, name in [('es', 'Español'), ('en', 'English'),
                           ('fr', 'Français'), ('it', 'Italiano'), ('de', 'Deutsch')]:
            self.lang_combo.addItem(name, code)
        self.lang_combo.setFixedWidth(115)
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        hbar.addWidget(self.lang_combo)
        self.check_on_top = QCheckBox()
        self.check_on_top.toggled.connect(self.toggle_on_top)
        hbar.addWidget(self.check_on_top)
        outer.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(400)
        scroll.setMaximumWidth(670)
        left = QWidget()
        self.controls = QVBoxLayout(left)
        self.controls.setContentsMargins(14, 12, 14, 18)
        self.controls.setSpacing(12)
        scroll.setWidget(left)
        splitter.addWidget(scroll)
        self._make_capture()
        self._make_profiles()
        self._make_text()
        self._make_coords()
        self._make_style()
        self._make_logo()
        self._make_alignment()
        self._make_coffee()
        self.controls.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 14)
        right_layout.setSpacing(11)
        row = QHBoxLayout()
        self.preview_title = QLabel()
        self.preview_title.setStyleSheet('font-weight:700;font-size:16px;color:#E9F1FF;')
        row.addWidget(self.preview_title)
        row.addStretch()
        self.btn_refresh = self._button('capture', self.capture_base_image)
        row.addWidget(self.btn_refresh)
        right_layout.addLayout(row)
        self.preview = PreviewCanvas()
        self.preview.positionChanged.connect(self.drag_position)
        self.preview.selectedChanged.connect(self.selection_changed)
        right_layout.addWidget(self.preview, 1)
        self.instruction = QLabel()
        self.instruction.setObjectName('Muted')
        right_layout.addWidget(self.instruction)
        self.info = QLabel()
        self.info.setObjectName('Status')
        self.info.setWordWrap(True)
        right_layout.addWidget(self.info)
        self.btn_apply = self._button('apply', self.apply_annotation)
        self.btn_apply.setObjectName('Primary')
        self.btn_apply.setEnabled(False)
        right_layout.addWidget(self.btn_apply)
        splitter.addWidget(right)
        splitter.setSizes([490, 850])

    def _make_capture(self):
        form = self._group('capture_group')
        self.lbl_capture = QLabel()
        self.lbl_capture.setObjectName('Muted')
        self.lbl_capture.setWordWrap(True)
        form.addRow(self.lbl_capture)

    def _make_profiles(self):
        form = self._group('profiles_group')
        self.profile_combo = QComboBox()
        self._update_profile_combo()
        form.addRow(self.profile_combo)
        row = QHBoxLayout()
        for key, handler in [('load', self.load_profile),
                             ('save_as', self.save_profile), ('delete', self.delete_profile)]:
            row.addWidget(self._button(key, handler))
        form.addRow(row)
        self._hint(form, 'profile_help')

    def _make_text(self):
        form = self._group('text_group')
        self.show_title = QCheckBox()
        self._connect(self.show_title)
        form.addRow(self.show_title)
        self.edit_sci = QLineEdit()
        self.edit_sci.setPlaceholderText('M31 / NGC 224')
        self._connect(self.edit_sci)
        self._row(form, 'scientific', self.edit_sci)
        self.edit_common = QLineEdit()
        self.edit_common.setPlaceholderText('Andromeda Galaxy')
        self._connect(self.edit_common)
        self._row(form, 'common', self.edit_common)
        self.stack_text = QCheckBox()
        self.stack_text.toggled.connect(self.changed)
        form.addRow(self.stack_text)
        self._hint(form, 'stack_help')
        self.title_x, self.title_y = self._positions(form, 'pos_title')
        self._hint(form, 'text_help')

    def _make_coords(self):
        form = self._group('coords_group')
        self.show_coords = QCheckBox()
        self._connect(self.show_coords)
        form.addRow(self.show_coords)
        self.label_coords = QLabel()
        self.label_coords.setWordWrap(True)
        form.addRow(self.label_coords)
        form.addRow(self._button('read_plate', self.sync_with_siril_wcs))
        self.edit_ra = QLineEdit()
        self.edit_ra.setPlaceholderText('11h 20m 15s')
        self.edit_dec = QLineEdit()
        self.edit_dec.setPlaceholderText('+13° 05\' 40"')
        self._row(form, 'ra_manual', self.edit_ra)
        self._row(form, 'dec_manual', self.edit_dec)
        self.edit_ra.textChanged.connect(self.changed)
        self.edit_dec.textChanged.connect(self.changed)
        form.addRow(self._button('use_manual', self.apply_manual_coords))
        self.coords_x, self.coords_y = self._positions(form, 'pos_coords')

    def _make_style(self):
        form = self._group('style_group')
        self.font_size = self._spin(2, 200, 0, ' px')
        self._row(form, 'font_size', self.font_size)
        self.text_opacity = self._spin(0, 100, 0)
        self._row(form, 'opacity', self.text_opacity)
        self.btn_color = self._button('color', self.pick_color)
        self._row(form, 'color', self.btn_color)

    def _make_logo(self):
        form = self._group('logo_group')
        self.show_logo = QCheckBox()
        self._connect(self.show_logo)
        form.addRow(self.show_logo)
        self.logo_path_label = QLabel()
        self.logo_path_label.setObjectName('Muted')
        self.logo_path_label.setWordWrap(True)
        form.addRow(self.logo_path_label)
        row = QHBoxLayout()
        row.addWidget(self._button('logo_choose', self.choose_logo))
        row.addWidget(self._button('remove', self.remove_logo))
        form.addRow(row)
        self.logo_size = self._spin(0.5, 100)
        self._row(form, 'logo_width', self.logo_size)
        self.logo_opacity = self._spin(0, 100, 0)
        self._row(form, 'logo_opacity', self.logo_opacity)
        self.logo_x, self.logo_y = self._positions(form, 'pos_logo')
        self._hint(form, 'logo_help')

    def _make_alignment(self):
        form = self._group('layout_group')
        self._hint(form, 'align_help')
        self.margin = self._spin(0, 30)
        self._row(form, 'margin', self.margin)
        form.addRow(self._button('bottom_align', lambda: self.align_elements('bottom')))
        form.addRow(self._button('side_align', lambda: self.align_elements('sides')))
        self.center_combo = QComboBox()
        self._row(form, 'center_item', self.center_combo)
        form.addRow(self._button('center_distribute', lambda: self.align_elements('distribute')))

    def _make_coffee(self):
        form = self._group('coffee_group')
        coffee = self._button('coffee_button', self.open_coffee)
        coffee.setObjectName('Coffee')
        coffee.setToolTip(COFFEE_URL)
        form.addRow(coffee)

    def _update_profile_combo(self, selected=None):
        previous = selected if selected is not None else self.profile_combo.currentData() if self.profile_combo.count() else None
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(self.t('profile_choose'), '')
        for name in sorted(self.storage['profiles']):
            self.profile_combo.addItem(name, name)
        i = self.profile_combo.findData(previous)
        self.profile_combo.setCurrentIndex(i if i >= 0 else 0)
        self.profile_combo.blockSignals(False)

    def _update_center_combo(self):
        previous = self.center_combo.currentData()
        options = [('text_stack', 'center_block'), ('logo', 'center_logo')] if self.stack_text.isChecked() else [
            ('title', 'center_title'), ('coords', 'center_coords'), ('logo', 'center_logo')]
        self.center_combo.blockSignals(True)
        self.center_combo.clear()
        for item, key in options:
            self.center_combo.addItem(self.t(key), item)
        index = self.center_combo.findData(previous)
        self.center_combo.setCurrentIndex(index if index >= 0 else 0)
        self.center_combo.blockSignals(False)

    def _update_stack_ui(self):
        stacked = self.stack_text.isChecked()
        # Title pair locates the entire group when stacked; separate coords retain
        # their previous settings and remain available on unstacking.
        self.coords_x.setEnabled(not stacked)
        self.coords_y.setEnabled(not stacked)
        self.labels['pos_coords'].setEnabled(not stacked)
        self.labels['pos_title'].setText(self.t('pos_stack' if stacked else 'pos_title'))
        self._update_center_combo()

    def _translate_ui(self):
        lang = self.state.get('language', 'es')
        self.lang_label.setText(self.t('language') + ':')
        self.check_on_top.setText(self.t('always_top'))
        for key, group in self.groups.items():
            group.setTitle(self.t(key))
        for key, label in self.labels.items():
            label.setText(self.t(key))
        for key, hint in self.hints.items():
            hint.setText(self.t(key))
        for key, button in self.buttons.items():
            if key == 'color':
                continue
            button.setText(self.t(key))
            if key in ('bottom_align', 'side_align', 'center_distribute'):
                button.setToolTip(self.t(key.replace('_align', '_tip').replace('center_distribute', 'center_tip')))
        self.show_title.setText(self.t('show_names'))
        self.stack_text.setText(self.t('stack'))
        self.show_coords.setText(self.t('show_coords'))
        self.show_logo.setText(self.t('show_logo'))
        self.preview_title.setText(self.t('preview_title'))
        self.preview.language = lang
        self.preview.setToolTip(self.t('preview_help'))
        self.preview.update()
        self._update_profile_combo()
        self._update_stack_ui()
        self._refresh_coord_label()
        if not self.state.get('logo_path'):
            self.logo_path_label.setText(self.t('logo_none'))
        elif self.logo is None:
            self.logo_path_label.setText(self.t('logo_error', error=Path(self.state['logo_path']).name))
        self.instruction.setText(self.t('preview_help'))
        self._refresh_color_button()
        if self.clean_snapshot is None:
            self.lbl_capture.setText(self.t('image_none'))
        # The preview hint already appears above. Do not repeat it in status.

    def change_language(self, index):
        if self._updating or index < 0:
            return
        lang = self.lang_combo.currentData()
        if lang not in ('es', 'en', 'fr', 'it', 'de'):
            return
        self.state['language'] = lang
        self._translate_ui()
        self.changed()

    def _restore_state(self):
        self._updating = True
        try:
            st = self.state
            for key, widget in [
                ('scientific', self.edit_sci), ('common', self.edit_common),
                ('manual_ra', self.edit_ra), ('manual_dec', self.edit_dec)]:
                widget.setText(str(st.get(key, '')))
            for key, widget in [
                ('title_x', self.title_x), ('title_y', self.title_y),
                ('coords_x', self.coords_x), ('coords_y', self.coords_y),
                ('logo_x', self.logo_x), ('logo_y', self.logo_y),
                ('font_size', self.font_size), ('text_opacity', self.text_opacity),
                ('logo_size', self.logo_size), ('logo_opacity', self.logo_opacity),
                ('align_margin', self.margin)]:
                try:
                    value = float(st.get(key, DEFAULTS[key]))
                except (ValueError, TypeError):
                    value = float(DEFAULTS[key])
                widget.setValue(round(value) if isinstance(widget, QSpinBox) else value)
            for key, widget in [
                ('show_title', self.show_title), ('show_coords', self.show_coords),
                ('show_logo', self.show_logo), ('always_on_top', self.check_on_top),
                ('stack_text', self.stack_text)]:
                widget.setChecked(bool(st.get(key, DEFAULTS[key])))
            i = self.lang_combo.findData(st.get('language', 'es'))
            self.lang_combo.setCurrentIndex(i if i >= 0 else 0)
            self._read_logo(silent=True)
        finally:
            self._updating = False
        flag = Qt.WindowType.WindowStaysOnTopHint
        if bool(self.windowFlags() & flag) != bool(self.state.get('always_on_top', False)):
            visible = self.isVisible()
            self.setWindowFlag(flag, bool(self.state.get('always_on_top', False)))
            if visible:
                self.show()
        self._translate_ui()
        self.changed()

    def _collect(self):
        st = dict(self.state)
        for key, widget in [
            ('scientific', self.edit_sci), ('common', self.edit_common),
            ('manual_ra', self.edit_ra), ('manual_dec', self.edit_dec)]:
            st[key] = widget.text()
        for key, widget in [
            ('title_x', self.title_x), ('title_y', self.title_y),
            ('coords_x', self.coords_x), ('coords_y', self.coords_y),
            ('logo_x', self.logo_x), ('logo_y', self.logo_y),
            ('font_size', self.font_size), ('text_opacity', self.text_opacity),
            ('logo_size', self.logo_size), ('logo_opacity', self.logo_opacity),
            ('align_margin', self.margin)]:
            st[key] = widget.value()
        for key, widget in [
            ('show_title', self.show_title), ('show_coords', self.show_coords),
            ('show_logo', self.show_logo), ('always_on_top', self.check_on_top),
            ('stack_text', self.stack_text)]:
            st[key] = widget.isChecked()
        self.state = st

    def changed(self, *_):
        if self._updating:
            return
        sender = self.sender()
        if sender in (self.title_x, self.title_y):
            self._preferred_text = 'title'
        elif sender in (self.coords_x, self.coords_y):
            self._preferred_text = 'coords'
        if sender is self.stack_text:
            self._update_stack_ui()
        self._collect()
        self.render_timer.start(75)
        self.save_timer.start(500)

    def persist(self):
        if self._updating:
            return
        self._collect()
        ephemeral = {'scientific', 'common', 'manual_ra', 'manual_dec'}
        self.storage['current'] = {k: v for k, v in self.state.items() if k not in ephemeral}
        try:
            save_data(self.storage)
        except OSError as e:
            self.info.setText(self.t('settings_error', error=e))

    def save_profile(self):
        name, ok = QInputDialog.getText(self, self.t('save_profile'), self.t('name_profile'))
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self.storage['profiles'] and QMessageBox.question(
            self, self.t('overwrite_profile'), self.t('confirm_overwrite', name=name)
        ) != QMessageBox.StandardButton.Yes:
            return
        self._collect()
        excludes = {'scientific', 'common', 'manual_ra', 'manual_dec', 'language'}
        self.storage['profiles'][name] = {k: v for k, v in self.state.items() if k not in excludes}
        self.persist()
        self._update_profile_combo(name)
        self.info.setText(self.t('profile_saved', name=name))

    def load_profile(self):
        name = self.profile_combo.currentData()
        if name not in self.storage['profiles']:
            return
        self._collect()
        excludes = {'scientific', 'common', 'manual_ra', 'manual_dec', 'language'}
        self.state.update({k: v for k, v in self.storage['profiles'][name].items()
                           if k in DEFAULTS and k not in excludes})
        self._restore_state()
        self.persist()
        self.info.setText(self.t('profile_loaded', name=name))

    def delete_profile(self):
        name = self.profile_combo.currentData()
        if name not in self.storage['profiles']:
            return
        if QMessageBox.question(self, self.t('delete_profile'), self.t('confirm_delete', name=name)) != QMessageBox.StandardButton.Yes:
            return
        del self.storage['profiles'][name]
        self.persist()
        self._update_profile_combo()

    def toggle_on_top(self, enabled):
        if self._updating:
            return
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(enabled))
        self.show()
        self.changed()

    def pick_color(self):
        col = QColorDialog.getColor(QColor(self.state['text_color']), self, self.t('text_color'))
        if col.isValid():
            self.state['text_color'] = col.name()
            self._refresh_color_button()
            self.changed()

    def _refresh_color_button(self):
        col = str(self.state.get('text_color', '#FFFFFF'))
        if not QColor(col).isValid():
            col = '#FFFFFF'
        self.btn_color.setText(col.upper())
        self.btn_color.setStyleSheet(f'border-left: 6px solid {col};')

    def _read_logo(self, silent=False):
        path = str(self.state.get('logo_path', ''))
        self.logo = None
        self.logo_path_label.setText(Path(path).name if path else self.t('logo_none'))
        if path:
            try:
                self.logo = prepare_logo(path)
            except (OSError, ValueError) as e:
                self.logo_path_label.setText(self.t('logo_error', error=Path(path).name))
                if not silent:
                    QMessageBox.warning(self, self.t('logo_choose'), self.t('logo_error', error=e))

    def choose_logo(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, self.t('select_logo'), str(Path.home()),
            'Images (*.png *.webp *.tif *.tiff *.jpg *.jpeg *.bmp);;All files (*)')
        if not filename:
            return
        self.state['logo_path'] = filename
        self._read_logo()
        self.changed()

    def remove_logo(self):
        self.state['logo_path'] = ''
        self.logo = None
        self.logo_path_label.setText(self.t('logo_none'))
        self.changed()

    def open_coffee(self):
        """Open the author's contribution page in the system's default browser."""
        if not QDesktopServices.openUrl(QUrl(COFFEE_URL)):
            QMessageBox.warning(self, self.t('coffee_button'),
                                self.t('coffee_open_failed'))

    def _log(self, message, error=False):
        try:
            self.siril.log(message, s.LogColor.RED if error else s.LogColor.GREEN)
        except Exception:
            print(message)
        self.info.setText(message)

    def _refresh_coord_label(self):
        if self.coords:
            ra, dec = COORD_PREFIXES.get(self.state.get('language', 'es'), COORD_PREFIXES['es'])
            self.label_coords.setText(f'{ra} {self.coords[0]}  /  {dec} {self.coords[1]}')
        else:
            self.label_coords.setText(self.t('coords_pending'))

    def capture_base_image(self):
        try:
            native = normalize_pixels(self.siril.get_image_pixeldata(preview=False))
            if native.dtype not in (np.float32, np.uint16):
                raise ValueError(f'Native format is not float32/uint16: {native.dtype}')
            previous = self.capture_filename
            previous_shape = self.clean_snapshot.shape if self.clean_snapshot is not None else None
            try:
                current = self.siril.get_image_filename()
            except Exception:
                current = None
            if self.clean_snapshot is not None and (
                (previous and current and previous != current) or previous_shape != native.shape
            ):
                self.coords = None
                self.label_coords.setText(self.t('coords_reset'))
            # Keep an independent immutable reference image: some sirilpy
            # implementations can expose a buffer view rather than an owned copy.
            self.clean_snapshot = native.copy(order='C')
            self.capture_filename = current
            self.original_size = (native.shape[2], native.shape[1])
            try:
                visual = normalize_pixels(self.siril.get_image_pixeldata(preview=True))
                if visual.shape != native.shape:
                    raise ValueError('Preview size mismatch')
                base = rgb8_from_siril(visual)
            except Exception:
                base = rgb8_from_siril(native)
            self.preview_base = base
            self.preview_base.thumbnail(PREVIEW_MAX, Image.Resampling.LANCZOS)
            self.lbl_capture.setText(f'{self.original_size[0]} × {self.original_size[1]} px  /  {native.dtype}')
            self.btn_apply.setEnabled(True)
            self._log(self.t('image_captured'))
            self.render_preview()
        except Exception as e:
            self.clean_snapshot = None
            self.preview_base = None
            self.btn_apply.setEnabled(False)
            self.lbl_capture.setText(self.t('image_unavailable'))
            self._log(self.t('image_capture_error', error=e), error=True)

    def sync_with_siril_wcs(self):
        try:
            from astropy.io import fits
            from astropy.wcs import WCS
            header_text = self.siril.get_image_fits_header(return_as='str')
            header = None
            if isinstance(header_text, str) and header_text.strip():
                try:
                    header = fits.Header.fromstring(header_text, sep='\n')
                    if 'CRVAL1' not in header:
                        header = fits.Header.fromstring(header_text, sep='')
                except Exception:
                    header = None
            if header is None or 'CRVAL1' not in header:
                filename = self.siril.get_image_filename()
                if filename and os.path.isfile(filename):
                    with fits.open(filename) as hdul:
                        header = hdul[0].header.copy()
            if header is None or 'CRVAL1' not in header or 'CRVAL2' not in header:
                raise ValueError(self.t('coords_no_wcs'))
            wcs = WCS(header, naxis=2)
            if not wcs.has_celestial:
                raise ValueError(self.t('coords_invalid_wcs'))
            shape = self.siril.get_image_shape()
            center = wcs.pixel_to_world((shape[2]-1)/2, (shape[1]-1)/2)
            ra = center.ra.to_string(unit='hour', sep=('h ', 'm ', 's'), precision=0, pad=True)
            dec = center.dec.to_string(unit='degree', sep=('° ', "' ", '"'), precision=0,
                                       pad=True, alwayssign=True)
            self.coords = (ra, dec)
            self._refresh_coord_label()
            self._log(self.t('coords_read'))
            self.changed()
        except Exception as e:
            self._log(self.t('coords_error', error=e), error=True)

    def apply_manual_coords(self):
        ra, dec = self.edit_ra.text().strip(), self.edit_dec.text().strip()
        if not (ra and dec):
            QMessageBox.warning(self, self.t('coords_group'), self.t('manual_both'))
            return
        self.coords = (ra, dec)
        self._refresh_coord_label()
        self._log(self.t('manual_applied'))
        self.changed()

    def _set_positions(self, changes):
        """Set widget positions atomically to prevent intermediate render races."""
        widgets = dict(title_x=self.title_x, title_y=self.title_y,
                       coords_x=self.coords_x, coords_y=self.coords_y,
                       logo_x=self.logo_x, logo_y=self.logo_y)
        self._updating = True
        try:
            for key, value in changes.items():
                if key in widgets:
                    widgets[key].setValue(clamp(value))
        finally:
            self._updating = False
        self._collect()

    def _prevent_overlap(self, preserve='coords'):
        if self.state.get('stack_text') or self.preview_base is None or not self.coords:
            return False
        new = resolve_text_overlap(self.original_size, self.state, self.coords, preserve=preserve)
        diffs = {k: new[k] for k in ('title_x', 'title_y', 'coords_x', 'coords_y')
                 if abs(float(new[k])-float(self.state[k])) > 0.0001}
        if diffs:
            self._set_positions(diffs)
            self.save_timer.start(500)
        return bool(diffs)

    def _active(self):
        """Returns effective draggable blocks in visual reading order."""
        boxes = layout_boxes(self.original_size, self.state, self.coords, self.logo)
        if 'text_stack' in boxes:
            return [k for k in ('text_stack', 'logo') if k in boxes], boxes
        return [k for k in ('title', 'coords', 'logo') if k in boxes], boxes

    def _layout_candidate(self, action):
        self._collect()
        w, h = self.original_size
        if self.preview_base is None or w <= 1 or h <= 1:
            return None, self.t('need_image')
        items, boxes = self._active()
        if 'logo' not in boxes:
            return None, self.t('need_logo')
        text_items = [k for k in items if k != 'logo']
        if not text_items:
            return None, self.t('need_text')
        margin = round(clamp(self.state['align_margin'], 0, 30) / 100 * w)
        gap = max(6, round(w * 0.015))
        dims = {key: (boxes[key][2]-boxes[key][0], boxes[key][3]-boxes[key][1]) for key in items}
        target = dict(self.state)
        # Every alignment operation uses the logo as the main visual reference.
        # Bottom alignment changes only Y; side margins only X.
        if action == 'bottom':
            bottom = max(boxes['logo'][3], max(dims[k][1]+max(2, round(h*0.01)) for k in items))
            if bottom > h:
                return None, self.t('fit_error')
            for key in text_items:
                value = (1-bottom/h)*100
                if key == 'text_stack':
                    target['title_y'] = value
                else:
                    target[key+'_y'] = value
            target['logo_y'] = (bottom-dims['logo'][1])/h*100
            # If free captions currently share an X anchor, setting a common
            # baseline would collide. Distribute X positions automatically.
            if layout_issues(self.original_size, target, self.coords, self.logo):
                order = ['text_stack', 'logo'] if 'text_stack' in items else ['title', 'coords', 'logo']
                if len(order) == 3:
                    xs = {'title': margin, 'coords': round((w-dims['coords'][0])/2),
                          'logo': w-margin-dims['logo'][0]}
                else:
                    xs = {'text_stack': margin, 'logo': w-margin-dims['logo'][0]}
                for key, x in xs.items():
                    target['title_x' if key == 'text_stack' else key+'_x'] = x/w*100
        elif action == 'sides':
            for key in text_items:
                target['title_x' if key == 'text_stack' else key+'_x'] = margin/w*100
            target['logo_x'] = (w-margin-dims['logo'][0])/w*100
        elif action == 'distribute':
            center = self.center_combo.currentData()
            if center not in items:
                center = items[0]
            # Three elements: one centred, the two others against side margins.
            # Stacked mode: one centred, the other against its opposite side.
            others = [k for k in items if k != center]
            xs = {center: round((w-dims[center][0])/2)}
            if len(others) == 2:
                xs[others[0]] = margin
                xs[others[1]] = w-margin-dims[others[1]][0]
            elif len(others) == 1:
                other = others[0]
                xs[other] = w-margin-dims[other][0] if center != 'logo' else margin
            for key, x in xs.items():
                target['title_x' if key == 'text_stack' else key+'_x'] = x/w*100
            bottom = max(boxes['logo'][3], max(dims[k][1]+max(2, round(h*0.01)) for k in items))
            if bottom > h:
                return None, self.t('fit_error')
            for key in text_items:
                target['title_y' if key == 'text_stack' else key+'_y'] = (1-bottom/h)*100
            target['logo_y'] = (bottom-dims['logo'][1])/h*100
        else:
            return None, self.t('fit_error')
        # Validation before committing avoids silently undoing user-requested alignment.
        if layout_issues(self.original_size, target, self.coords, self.logo):
            return None, self.t('fit_error')
        return {k: target[k] for k in ('title_x', 'title_y', 'coords_x', 'coords_y', 'logo_x', 'logo_y')}, ''

    def align_elements(self, action):
        changes, error = self._layout_candidate(action)
        if changes is None:
            self.info.setText(error)
            return
        self._set_positions(changes)
        self.render_timer.stop()
        self.render_preview()
        self.save_timer.start(500)
        self.info.setText(self.t('position_applied'))

    def render_preview(self):
        if self.preview_base is None:
            return
        try:
            self._prevent_overlap(getattr(self, '_preferred_text', 'coords'))
            self._preferred_text = 'coords'
            scale = self.preview_base.width / self.original_size[0]
            layer, boxes = paint_annotations(self.preview_base.size, self.state,
                                             coords=self.coords, logo=self.logo, font_scale=scale)
            base = self.preview_base.copy().convert('RGBA')
            composed = Image.alpha_composite(base, layer).convert('RGB')
            self.preview.set_preview(composed, boxes)
            if layout_issues(self.original_size, self.state, self.coords, self.logo):
                self.instruction.setText(self.t('overlap_warning'))
            else:
                self.instruction.setText(self.t('preview_help'))
        except Exception as e:
            self.info.setText(self.t('preview_error', error=e))

    def drag_position(self, key, dx, dy):
        if key not in ('title', 'coords', 'logo', 'text_stack'):
            return
        b = self.preview._boxes.get(key)
        if not b or self.preview_base is None:
            return
        w, h = self.preview_base.size
        dx = max(-b[0]/w*100, min((w-b[2])/w*100, dx))
        dy = max(-b[1]/h*100, min((h-b[3])/h*100, dy))
        real_key = 'title' if key == 'text_stack' else key
        xwidget, ywidget = getattr(self, real_key+'_x'), getattr(self, real_key+'_y')
        if key in ('title', 'coords'):
            self._preferred_text = key
        self._set_positions({real_key+'_x': xwidget.value()+dx,
                             real_key+'_y': ywidget.value()+(dy if key == 'logo' else -dy)})
        self.render_timer.stop()
        self.render_preview()
        self.save_timer.start(500)

    def selection_changed(self, key):
        names = {'title': 'preview_title_selected', 'coords': 'preview_coords_selected',
                 'logo': 'preview_logo_selected', 'text_stack': 'preview_stack'}
        self.instruction.setText(self.t(names.get(key, 'preview_help')))

    def apply_annotation(self):
        if self.clean_snapshot is None:
            return
        self.btn_apply.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            shape = self.siril.get_image_shape()
            if tuple(shape) != tuple(self.clean_snapshot.shape):
                raise RuntimeError(self.t('image_changed'))
            try:
                current_filename = self.siril.get_image_filename()
                if self.capture_filename and current_filename and self.capture_filename != current_filename:
                    raise RuntimeError(self.t('image_changed'))
            except RuntimeError:
                raise
            except Exception:
                pass
            self._prevent_overlap()
            if layout_issues(self.original_size, self.state, self.coords, self.logo):
                raise ValueError(self.t('overlap_warning'))
            full, _ = paint_annotations(self.original_size, self.state, self.coords, self.logo)
            output = blend_overlay_into_siril(self.clean_snapshot, full)
            with self.siril.image_lock():
                # Verify the current pixels while Siril's processing thread is
                # locked. A file name and dimensions alone cannot detect edits.
                active_pixels = normalize_pixels(self.siril.get_image_pixeldata(preview=False))
                if (active_pixels.shape != self.clean_snapshot.shape or
                        active_pixels.dtype != self.clean_snapshot.dtype or
                        not np.array_equal(active_pixels, self.clean_snapshot, equal_nan=True)):
                    raise RuntimeError(self.t('image_pixels_changed'))
                self.siril.undo_save_state('SGA_AstroAnnotator')
                success = self.siril.set_image_pixeldata(output)
                if success is False:
                    raise RuntimeError(self.t('apply_rejected'))
            self.persist()
            self._log(self.t('apply_success'))
        except Exception as e:
            self._log(self.t('apply_error_detail', error=e), error=True)
            QMessageBox.warning(self, self.t('apply_error'), str(e))
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_apply.setEnabled(self.clean_snapshot is not None)

    def closeEvent(self, event):
        self.save_timer.stop()
        self.persist()
        super().closeEvent(event)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        siril = s.SirilInterface()
        siril.connect()
    except Exception as e:
        QMessageBox.critical(None, 'Siril', f'Cannot connect to Siril:\n{e}')
        return 1
    window = AstroAnnotator(siril)
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
