# Aufruf externer Diagnoseprogramme
## Begrenzter Prozessaufruf
subprocess.run wartet auf das Ende eines gestarteten Programms. Mit check=True wird ein von null verschiedener Rückgabecode als CalledProcessError sichtbar. capture_output=True erfasst Standardausgabe und Fehlerausgabe getrennt. Für Argumente wird eine Liste und shell=False verwendet, damit ein Dateiname nicht als zusätzliche Shell-Anweisung interpretiert wird.
## Zeitüberschreitung
Wenn der Timeout von subprocess.run abläuft, wird der direkte Kindprozess beendet und abgewartet, bevor TimeoutExpired erneut ausgelöst wird. Der Start des Prozesses selbst kann die beobachtete Gesamtdauer verlängern. Dieses Verhalten ist nicht gleichbedeutend mit dem Abbruch einer beliebigen bereits laufenden Python-Thread-Funktion. Ein Werkzeugprotokoll unterscheidet Rückgabefehler, Startfehler und Zeitüberschreitung, anstatt alle drei als leeres erfolgreiches Ergebnis darzustellen.
```python
completed = subprocess.run(["diag", "--status"], check=True,
                           capture_output=True, text=True, timeout=4)
```
