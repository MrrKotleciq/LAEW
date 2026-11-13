# INI-Konfiguration des Messdienstes
## Typen und boolesche Werte
ConfigParser speichert Konfigurationswerte als Zeichenketten. Für eine boolesche Option wird getboolean verwendet; bool("false") ist wegen der nichtleeren Zeichenkette kein geeigneter Ersatz. Die speziellen Zugriffsmethoden konvertieren Zahlen und boolesche Werte und melden ungültige Eingaben. Ein fehlender optionaler Wert kann über fallback behandelt werden.
```python
enabled = config.getboolean("capture", "enabled", fallback=False)
period = config.getint("capture", "period_ms")
```
## Standardwerte und Überlagerung
Werte aus DEFAULT stehen auch in regulären Abschnitten zur Verfügung. Mehrere eingelesene Konfigurationsdateien können frühere Werte überlagern; die später gelesene Datei hat bei Konflikten Vorrang. Abschnittsnamen bleiben unterscheidbar, während Optionsnamen standardmäßig ohne Beachtung der Großschreibung behandelt werden. Vor der Freigabe eines geänderten Profils werden die tatsächlich aufgelösten Werte geprüft, nicht nur die zuletzt editierte Datei.
