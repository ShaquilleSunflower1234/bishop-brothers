# Bishop Brothers 1.0.0 — Windows

**[Download Bishop Brothers for Windows](https://github.com/ShaquilleSunflower1234/bishop-brothers/releases/latest/download/BishopBrothers-1.0.0-Windows.zip)** · [Release page and checksums](https://github.com/ShaquilleSunflower1234/bishop-brothers/releases/latest)

Extract the ZIP, open BishopBrothers.exe, plug in your Xbox 360 USB, select the detected save, and click **Add Bishops**.

Free to use. Donations are optional and never unlock app features. No Horizon or separate signing setup is required.

Open **BishopBrothers.exe** with your Xbox 360 USB plugged in. The app scans connected Windows drives that have a Content folder and finds Fight Night Champion boxer saves inside the numbered Xbox folders. Choose the profile/save in the list and click **Add Bishops**. It handles the numbered file path for you.

For a copy already on your PC, drop the entire **Content folder** into the window, or click **Use a copied folder** and select the USB root, Content folder, or parent of your copied Xbox folder. You can also drop a folder onto the executable to scan it at launch. Ordinary native Windows Content folders are supported; older Xbox USB storage stored inside a FATX image is not supported.

Profile names are taken from an available profile package's display name. If no usable name is available, the app shows **Xbox profile ending …** and the save date so that it does not invent a gamertag. Multiple saves are listed separately and require a selection.

The app adds Ex-Con Andre Bishop (2514) and Raymond Bishop (2520) records to verified empty slots. An existing record with the same ID is kept, including its clothing choices. An untouched backup and prepared copy are stored under **%LOCALAPPDATA%\BishopMerge\Exports** before replacement. Click **Open backups** to view them. The app returns a verified signed save to the exact original numbered path. Scanning alone never changes a save.

## One-click signing and transfer

Signing is now built in. You do not need Horizon, a personal signing file, or a separate Finish click. **Add Bishops** backs up, merges, rebuilds package hashes, signs, verifies, and returns the save automatically. The app includes the CON signing parameters and certificate published in unknownv2's Horizon source under the Unlicense. The parameters were taken from commit **ad518325cef804ad3805ff08824c4fded94f9570**, validated against the source blob, and stored in a minimal signing container. No user's private console keyvault was extracted. Provenance is recorded in assets/signer-provenance.json; the license is included in Third-party licenses/Horizon-Unlicense.txt.

Normal flow: plug in USB, select the detected profile/save if needed, click **Add Bishops**, and wait for the completion message. The **Resume interrupted update** button is only for recovery after interruption or a failed return. **Recovery options → Start fresh (keep all backups)** can clear an old pending job. Unsigned or mismatched copies are never returned to USB; changes to the source after backup cause the app to stop.

After the app confirms the signed save has been returned to its original USB folder, safely eject the USB. Use the Xbox 360 dashboard to copy **Fight Night Champion Boxers** to Cloud Saved Games. Xbox One uses that cloud copy through backward compatibility; it does not import this save directly from a PC USB drive. Preserve any existing cloud copy before replacing it. If you used a copied PC folder, the updated copy is placed there; copy that Content tree back to the USB using the same structure.

## What has and has not been validated

The donor Bishops came from the earlier save that the user confirmed worked on Xbox One. The merge passed local preservation, hashing, duplicate prevention, malformed-input, and signing tests. Folder discovery, ownership, automatic return, backup preservation, invalid-signature blocking, and changed-source protection passed on copied folders. The built-in signer uses the same certificate as the earlier Xbox-tested Horizon save and reproduces that known save byte for byte when re-signing it. The owner then reported that the new app succeeded in their Xbox test. Local signature checks do not independently establish Microsoft's certificate trust chain or revocation status, and success on this tested setup does not establish compatibility with every save or console.

The inferred layout is deliberately restricted to the observed 14,000,028-byte TXT_BOXERS_SAVE payload with header values 83 and 83, the first 83 record slots, a single directory block, contiguous boxer allocation, and two-level STFS hashing. Unknown layouts, damaged packages, mismatched IDs, and nonempty unknown slots are rejected. The app inserts 1,004-byte records and leaves every other payload byte intact, including existing appearance blobs. Additional schemas and fully occupied saves are not supported.

The project owner reported that the app succeeded in their Xbox test on October 14, 2026. This is a user-reported success, not independent verification of every console, profile, save layout, or online mode. Keep your backup and verify both fighters and your existing boxers after transfer.

## Source

Python 3.11+ with tkinter, tkinterdnd2, and cryptography. Run app.py, or build with PyInstaller using assets/bishops.bin as bundled data and collecting tkinterdnd2. The executable is portable and needs no Python installation. Source files are included for review and further development.

Signing material source: https://github.com/unknownv2/horizon-v2/blob/ad518325cef804ad3805ff08824c4fded94f9570/Horizon/Server/Config.cs (Unlicense). Format reference: https://github.com/SaveEditors/xecli (GPL-3.0; its implementation was not bundled). Earlier locally saved Velocity XContentHeader.cpp and STFS inspection results were also used as format references. The merge and folder handling were written for this project.
