# SGA_AstroAnnotator

Custom annotations for astronomical images in Siril.

Version: 1.0.0

Author: Sgalarreta · 2026

SGA_AstroAnnotator lets you add astronomical object names, equatorial coordinates, and your own logo to the image currently open in Siril. It includes an interactive preview so you can position elements before applying them to the image.

## Features

- Manually entered catalog or scientific names and common names.
- Read coordinates from a plate-solving solution (WCS), when available, or manually enter right ascension (RA) and declination (Dec).
- Stack text into a single block or position text blocks independently.
- Add a custom logo with adjustable size, opacity, and position. A PNG with a transparent background is recommended.
- Interactive preview: drag labels and the logo with the mouse to reposition them.
- Align bottom edges, match side margins, or distribute elements with one centered.
- Automatically save settings and reusable layout presets for other images.
- User interface available in Spanish, English, French, Italian, and German.
- Optional support button linking to Buy Me a Coffee.

The program places custom annotations. It does not include an automatic object catalog for detecting and labeling every source in an image.

## Requirements

Siril 1.4 or later, with Python scripting support (`sirilpy`). The script uses NumPy, Pillow, PyQt6, and Astropy. Siril manages its own Python environment, and the script automatically requests any missing dependencies. The first launch may take longer if dependencies need to be installed; an internet connection is required in that case.

The script is not designed to be launched as a standalone Python application outside Siril.

## Installation

1. Download `SGA_AstroAnnotator.py`.
2. Create a directory for your custom Siril scripts and copy the file into it.
3. In Siril, open `Preferences > Scripts` and add that directory to the script directories.
4. Refresh the script list using the refresh control, or restart Siril.
5. Run `SGA_AstroAnnotator` from Siril's scripts menu.

Do not modify Siril's internal application files or store this script inside the Siril application bundle on macOS.

## Basic usage

1. Open the image you want to annotate in Siril.
2. Click `Capture image from Siril` to refresh the preview.
3. Enable `Show names` and enter the catalog identifier and, optionally, the common name.
4. To add coordinates, click `Read plate-solved coordinates` if the image has a valid WCS solution. Alternatively, enter the values manually and click `Use manual coordinates`.
5. To include your own branding, choose an image file under `Custom logo` and enable its display.
6. Choose whether text blocks should be stacked or independent. Drag elements in the preview or adjust their positions using the controls.
7. Use the alignment buttons if you want to align the text with the logo, match margins, or distribute the blocks.
8. If you want to reuse the same arrangement, save it as a layout preset.
9. Click `Apply annotation in Siril`, then save the image from Siril using your preferred filename and format.

The preview does not change Siril's image pixels. The modification takes place only when you click `Apply annotation in Siril`. You can undo changes using Siril's usual history controls.

## Saved settings

Position, style, language, and logo file path are saved automatically in:

`~/.SGA_astroannotator/settings.json`

Layout presets save the arrangement for use with other images, but they do not copy manually entered object names or coordinates to those images. The logo path refers to the original file; if you move or delete that file, you will need to select it again.

If you used an earlier version, the program attempts to recover settings and presets stored in `~/.sgalarreta_astroannotator/settings.json`, without deleting the original file.

Positions are stored relative to image dimensions, which helps when reusing a layout at a different resolution. If labels or the logo do not fit, the program warns you and prevents applying overlapping elements or elements outside the image.

## Precautions and limitations

- The preview may use an automatic stretch to display the background. This stretch is for preview purposes only: applying annotations preserves the image currently loaded in Siril. If you want to export a stretched image, apply the stretch to the image data in Siril beforehand.
- Coordinates read from WCS require a valid astrometric solution in the image. Manually entered coordinates are displayed as text without astronomical validation.
- If the image open in Siril changes after it has been captured for preview, the program prevents applying annotations to the outdated snapshot. Click `Capture image from Siril` again.
- Preview and compositing have been checked using automated tests and simulated interface interactions. Full compatibility across all platforms and Siril versions has not been verified.
- Users are responsible for ensuring that they have the necessary rights to use any logos, photographs, or other elements they add to their images.

## Support and bug reports

If you encounter a problem, describe how to reproduce it, your Siril version, operating system, and the error message. You can report issues in the GitHub repository's *Issues* section.

## Support development

This script is free to use. If you find it useful and would like to support its maintenance and future development voluntarily, you can do so at:

https://buymeacoffee.com/sgalarreta

Donations are not required to use, modify, or redistribute the code under its license.

## Author and license

Copyright (c) 2026 Sgalarreta.

SGA_AstroAnnotator is distributed under the GNU General Public License, version 3 or later (`GPL-3.0-or-later`). See the `LICENSE` file for the full terms. The software is provided without warranty.

Siril, PyQt6, Pillow, Astropy, and NumPy are third-party projects with their own authors and licenses. Their source code is not included in this repository.
