# Fiktive Zeitspezifikation Atlas R3
## Messung und Grenzwerte
Die Werte in diesem originalen Testszenario gelten für ein erfundenes System. Der Produktionszyklus beträgt 750 Mikrosekunden; der zulässige absolute Zeitfehler beträgt höchstens 40 Mikrosekunden. Zeitabstände werden mit einer monotonen Uhr bestimmt. Die Wanduhr dient nur der lesbaren Datierung eines Prüfberichts und nicht der Berechnung der Zyklusdauer. Ein Sprung der Systemzeit darf deshalb keinen künstlichen Timingfehler auslösen.
## Freigabe nach einer Änderung
Nach einer Profiländerung werden mindestens 200 aufeinanderfolgende Zyklen geprüft. Überschreitet ein Zyklus die zulässige Fehlergrenze, bleibt die Freigabe gesperrt und der Bericht nennt die Nummer des ersten fehlerhaften Zyklus. Ein passender Mittelwert reicht nicht aus, wenn einzelne Zyklen den Grenzwert überschreiten. Diese Vorgabe gilt für R3 und wird nicht durch die Laborwerte des R2-Simulators ersetzt.
## Archivierung
Der Prüfbericht speichert die Profilkennung, die benutzte Uhrenart und die maximale absolute Abweichung. Er enthält keine Behauptung über zulässiges Motordrehmoment, CAN-Leitungslänge oder die Güte eines Sprachmodells. Andere Freigabebedingungen sind in den jeweiligen Verfahrensdokumenten definiert.
