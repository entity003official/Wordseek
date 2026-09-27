# soundcore Work D3200 integration

Protocol reference: https://github.com/tacshi/Soundcore/blob/main/PROTOCOL.md
Inspected 2026-09-27. Upstream is a Flutter/native project. No LICENSE file was present in the downloaded main snapshot. No Flutter implementation or dependencies are bundled into the app. The TypeScript adapter independently implements the documented packet and cryptographic formats; archive under work/ is reference material only.

## Implemented
- User-initiated Web Bluetooth device chooser filtered by D3200 service UUID.
- GATT notifications, fragmented frame reassembly, length and checksum checks; serialized writes and request timeouts.
- Device identity, battery levels, storage, recording state; explicit bind, start and pause controls.
- Paged recording list and offline BLE transfer with progress/cancellation.
- Ephemeral P-256 ECDH/HKDF session, AES-CTR file and packet decryption, rejection of mismatched keys/IDs and incomplete transfers.
- Local Ogg/Opus wrapping and IndexedDB import into the existing review flow. No audio/key upload on Bluetooth connect or import.
- Disconnect on route exit; does not implicitly pause hardware recording. Imported recording dates currently reflect import time.

## Requirements and limits
- Secure context (HTTPS or localhost), a browser supporting Web Bluetooth, and user selection in its device chooser. The embedded app browser might not expose Bluetooth.
- D3200 wire format as documented, including fixed 160-byte Opus packets. Firmware variation requires hardware confirmation.
- Max 100 MB per import. No automatic deletion or factory reset.
- Wi-Fi SoftAP export, classic SPP, OTA, iOS actions and Apple local transcription are not ported. Browser BLE is the active transfer path.
- Real-time BLE audio-to-ASR is not connected yet. Existing recording/analysis services remain the transcription path after import.
- TypeScript compilation completed; no live device or recorded-audio verification was performed.

Browser reference: https://developer.chrome.com/docs/capabilities/bluetooth
