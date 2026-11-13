# CAN-Diagnose im Prüfstand
## Bus-off und Wiederanlauf
Nach zu vielen Busfehlern kann die Schnittstelle in den Zustand BUS-OFF wechseln; dann findet keine normale Nachrichtenübertragung mehr statt. Ein positiver Wert für restart-ms aktiviert den automatischen Wiederanlauf nach der angegebenen Wartezeit in Millisekunden. Ohne diese Einstellung ist die automatische Wiederherstellung standardmäßig ausgeschaltet. Ein Anwenderprogramm kann Fehlerrahmen überwachen und den Wiederanlauf alternativ selbst anfordern.
```sh
ip link set can0 type can restart-ms 100
ip -details -statistics link show can0
```
## Diagnoseprotokoll
Die Detailanzeige enthält Zustand, Bitrate, Wiederanlaufparameter und Fehlerzähler. Für die Untersuchung einer instabilen Verbindung sollten diese Werte vor einer Änderung aufgezeichnet werden. Ein Wiederanlauf beseitigt nicht automatisch die physische Ursache eines Busfehlers. Die Anwendung unterscheidet eine konfigurierte Wartezeit von einer diagnostizierten Ursache und vermerkt beides in getrennten Feldern.
