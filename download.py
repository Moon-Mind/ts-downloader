"""Download TS (Transport Stream) video file from a website.

To use it:

- find the url of one of the TS file (for example, using the developer tools
  from Firefox or Chromium/Chrome)
- identify the counter in the url, and replace it with `{counter}` (this can be
  formatted if the counter must have a specific format, for example:
  `{counter:05d}`
- run the script: `python3 ts_downloader.py -o FILE.mp4 "URL_WITH_COUNTER"`

Bruno Oberle - 2002
"""

import argparse
import os
import subprocess
import tempfile
from urllib.error import URLError
from urllib.request import urlopen, Request


def download(template_url, tempdir):
    """Download the TS chunks and save them to temporary files."""
    ts_files = []
    
    # Verschiedene Startpunkte für den Counter ausprobieren
    start_counters = [0, 1]
    
    # Browser-ähnliche Header hinzufügen
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'de,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://hotleaks.tv/',
        'Origin': 'https://hotleaks.tv',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
    }
    
    # URL-Platzhalter explizit erkennen
    print(f"Überprüfe URL: {template_url}")
    if '{counter}' not in template_url and '{counter:' not in template_url:
        print("WARNUNG: URL enthält keinen {counter}-Platzhalter!")
        print("Versuch, direkt auf die URL zuzugreifen...")
        
        # Mehrere Zugriffsmethoden versuchen
        for delay in [0, 1, 2]:  # Verschiedene Verzögerungen testen
            if delay > 0:
                print(f"Warte {delay} Sekunden...")
                import time
                time.sleep(delay)
            
            try:
                print(f"Versuche Zugriff mit direktem URL-Request...")
                req = Request(template_url, headers=headers)
                u = urlopen(req, timeout=10)
                data = u.read()
                
                if not data:
                    print("Keine Daten erhalten.")
                    continue
                    
                # Datei speichern
                segment_path = os.path.join(tempdir, "segment_direct.ts")
                with open(segment_path, 'wb') as fh:
                    fh.write(data)
                ts_files.append(segment_path)
                print(f"Erfolgreich heruntergeladen: {len(data)} Bytes")
                return ts_files
            except URLError as e:
                print(f"Fehler beim direkten Zugriff: {e}")
                
        # Wenn alle direkten Versuche fehlschlagen, überprüfe, ob wir URL-Parameter anpassen können
        print("Versuche URL-Struktur zu analysieren und anzupassen...")
    
    # Test verschiedener Counter-Startpunkte
    for start_counter in start_counters:
        print(f"Versuche mit Start-Counter: {start_counter}")
        counter = start_counter
        success = False
        
        # Versuche verschiedene Formatierungen für den Counter
        formats = ["{}", "{:d}", "{:05d}"]
        
        for fmt in formats:
            counter_fmt = fmt.format(counter)
            # Ersetze {counter} mit dem aktuellen Format
            url = template_url.replace("{counter}", counter_fmt)
            
            print(f"Teste URL: {url}")
            try:
                req = Request(url, headers=headers)
                u = urlopen(req, timeout=10)
                data = u.read()
                
                # Wenn erfolgreich, verwende dieses Format
                if data and len(data) >= 188 and data[0] == 0x47:
                    print(f"Erfolg! Verwende Format: {fmt}")
                    success = True
                    break
            except URLError as e:
                print(f"Fehler mit Format {fmt}: {e}")
                continue
        
        if not success:
            continue  # Versuche nächsten Startpunkt
            
        # Wenn erfolgreich, beginne den eigentlichen Download
        while True:
            counter_fmt = fmt.format(counter)
            url = template_url.replace("{counter}", counter_fmt)
            print(f"Downloading {url}")
            
            try:
                req = Request(url, headers=headers)
                u = urlopen(req, timeout=10)
                data = u.read()
                
                # Überprüfen, ob die Daten ein TS-Segment sind
                if not data or len(data) < 188 or data[0] != 0x47:
                    print(f"Segment {counter} scheint ungültig zu sein. Ende des Streams erreicht.")
                    break
                    
                # Datei speichern
                segment_path = os.path.join(tempdir, f"segment_{counter:05d}.ts")
                with open(segment_path, 'wb') as fh:
                    fh.write(data)
                ts_files.append(segment_path)
                counter += 1
            except URLError as e:
                print(f"Fehler beim Herunterladen von Segment {counter}: {e}")
                break
                
        if ts_files:  # Wenn wir Dateien haben, beende die Schleife
            break
    
    return ts_files


def concat_ts_files(ts_files, output_path):
    """Konkateniert TS-Dateien mit FFmpeg."""
    # Erstelle eine Dateiliste für FFmpeg
    list_file = os.path.join(os.path.dirname(ts_files[0]), "filelist.txt")
    with open(list_file, 'w') as f:
        for ts_file in ts_files:
            f.write(f"file '{os.path.basename(ts_file)}'\n")
    
    # FFmpeg-Befehl zum Konkatenieren ohne Neucodierung
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-c', 'copy',
        '-y',
        output_path
    ]
    
    print(f"Führe aus: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    return output_path


def convert_ts_to_mp4(ts_path, mp4_path):
    """Convert TS file to MP4 format using ffmpeg with improved error handling."""
    try:
        # Die robusteste Methode für die Konvertierung
        cmd = [
            'ffmpeg',
            '-fflags', '+genpts+igndts',
            '-i', ts_path,
            '-c:v', 'copy',           # Video-Stream kopieren
            '-c:a', 'aac',            # Audio in AAC konvertieren (falls nötig)
            '-strict', 'experimental',
            '-movflags', '+faststart',
            '-y',
            mp4_path
        ]
        print(f"Führe aus: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        print(f"Konvertierung erfolgreich: {mp4_path}")
    except subprocess.CalledProcessError as e:
        print(f"Fehler bei der Konvertierung: {e}")
        raise


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url_template",
        help="url template, must include {counter}"
    )
    parser.add_argument(
        "-o", dest="outfpath", required=True,
        help="output file"
    )
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    template_url = args.url_template
    
    with tempfile.TemporaryDirectory() as tempdir:
        # Segmente herunterladen
        ts_files = download(template_url, tempdir)
        
        if not ts_files:
            print("Keine TS-Segmente heruntergeladen.")
            return
            
        print(f"Heruntergeladen: {len(ts_files)} Segmente")
        
        # Segmente konkatenieren
        concat_ts_path = os.path.join(tempdir, "concat.ts")
        concat_ts_files(ts_files, concat_ts_path)
        
        # Zur MP4 konvertieren
        convert_ts_to_mp4(concat_ts_path, args.outfpath)


if __name__ == "__main__":
    main()
