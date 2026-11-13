"""Agent visual inspection notes; one explicit entry per inspected page, no automatic closure."""
VERIFIED='Verified correct'
CORRECTED='Corrected and verified against source'
VISUAL='Visual information unavailable in text'
UNRESOLVED='Unresolved — manual review required'
DEFECT='Extraction defect — blocks admission'

# All entries were compared with their original rendered page and actual excerpt.
A_NOTES={
 ('prusa-mini-pl',1):(CORRECTED,'Rotated native instruction text was reversed. Native object order repaired; remaining cover graphics are unavailable.'),
 ('prusa-mini-pl',15):(VERIFIED,'Both firmware/setup callouts and the six-item chapter list retain wording, order and scope. No missing technical prose found.'),
 ('prusa-mini-pl',22):(VISUAL,'First-layer checklist, source comparison caption and SuperPINDA note are retained. Fine visual acceptance criteria remain unavailable; no inferred dimensions added.'),
 ('prusa-mini-pl',31):(VISUAL,'Twelve published legend entries and profile/import restrictions are retained; raster UI positions remain unavailable.'),
 ('prusa-mini-pl',37):(VISUAL,'Five color-change steps and preview-before-export restriction retain order. Raster pointer location adds no available text.'),
 ('prusa-mk3s-pl',8):(VERIFIED,'No native merged table exists here: eleven safety instructions retain order, voltage/frequency alternatives, temperatures and negations. Table flag is false for this component.'),
 ('prusa-mk3s-pl',11):(CORRECTED,'Source chapter title was ordinary prose; heading restored. Accessory descriptions remain intact, with final sentence continuing onto the next source page.'),
 ('prusa-mk3s-pl',16):(UNRESOLVED,'Two columns were interleaved and PEI heading/callout tails split. Text columns and tails repaired; check/exclamation graphic polarity has no literal heading and remains unavailable pending manual disposition.'),
 ('prusa-mk3s-pl',19):(CORRECTED,'Final word of icon paragraph detached from its callout. Rejoined from native lines. ABS/textured-sheet negation and diagnostic-test condition remain intact.'),
 ('prusa-mk3s-pl',26):(VISUAL,'No merged technical table: loading/unloading text and source English note are retained. Filament-tip shape exists only in the image and is unavailable.'),
 ('prusa-mk3s-pl',36):(VERIFIED,'No table: 49 menu entries continue the page-35 tree. Values and conditional branches match indentation. This page excerpt is not a standalone menu root.'),
 ('prusa-mk3s-pl',37):(UNRESOLVED,'Layer-height and feed-rate values/negations are present. Icon scope begins in the middle of a paragraph; exact paragraph association remains unresolved. Graphic example timings are unavailable.'),
 ('prusa-mk3s-pl',39):(VISUAL,'Ten source Pronterface legend items, numbered labels and power-loss description are present. Raster UI values/targets are unavailable; no technical table is missing.'),
 ('prusa-mk3s-pl',47):(CORRECTED,'Stop-if-unfamiliar condition was split outside its warning. Complete native paragraph restored. Repeated source section number is publisher-authored and intentionally retained.'),
 ('prusa-mk3s-pl',59):(CORRECTED,'Last line of color-change note was outside the callout. Reattached once; three response branches and the same-material condition remain unchanged.'),
 ('prusa-mk3s-pl',69):(CORRECTED,'Literal advantages/disadvantages headings and their items were interleaved and falsely classified as icon notes. Columns now read separately with original headings; temperatures unchanged.'),
 ('prusa-mk4-de',1):(CORRECTED,'Rotated native cover text reversed; native object order repaired. Cover imagery remains unavailable.'),
 ('prusa-mk4-de',7):(CORRECTED,'Product label/value ordering corrupted by merged dimensions and multiline labels. Native cells restore MK4 matrix, units and three dimension qualifiers.'),
 ('prusa-mk4-de',8):(CORRECTED,'Same observed defect on this separately inspected MK3.9 table. Restored independently from its native cells; product applicability kept separate.'),
 ('prusa-mk4-de',16):(VISUAL,'Fifteen component legend entries and filament diameter are retained. Physical arrow targets remain unavailable.'),
 ('prusa-mk4-de',43):(VISUAL,'Fourteen interface legend entries retained in order. Raster UI and arrow targets remain unavailable.'),
 ('prusa-mk4s-en',1):(CORRECTED,'Rotated native instruction text reversed; native object order repaired. Other cover graphics are unavailable.'),
 ('prusa-mk4s-en',6):(CORRECTED,'Multiline property labels, frequency bands and dimensions were interleaved. Source cells restore relationships; two original product names and shared values remain once.'),
 ('prusa-mk4s-en',42):(VISUAL,'Fourteen published interface explanations retained. Raster positions and screenshot-only labels remain unavailable.'),
 ('prusa-mmu3-en',1):(CORRECTED,'Rotated native instruction text reversed; native object order repaired. Cover graphic details remain unavailable.'),
 ('prusa-mmu3-en',6):(UNRESOLVED,'Six published safety-symbol descriptions are retained, but small source icons have no explicit placeholder/row identity in the extraction. Mapping a symbol to an instruction needs manual disposition; no symbol descriptions generated.'),
 ('prusa-mmu3-en',7):(CORRECTED,'Manufacturer and dimensions labels were interleaved with values. Restored native table; printer-provided DC supply and indoor-use qualifier unchanged.'),
 ('prusa-xl-de',1):(CORRECTED,'Rotated native text reversed; repaired. Critical Infrastructure wording visible in cover artwork is not native extracted text, so that graphical edition label remains unavailable rather than transcribed.'),
 ('prusa-xl-de',9):(CORRECTED,'Native product table restored. Starred radio properties and the original Critical Infrastructure exclusion footnote remain linked by their source star markers.'),
 ('prusa-xl-de',15):(VISUAL,'Ten Single-Tool legend entries retain numbering; spatial arrow relationships remain unavailable.'),
 ('prusa-xl-de',16):(VISUAL,'Nine Single-Tool Nextruder entries and non-interchangeability callout are retained. Graphic positions remain unavailable; callout is not a chapter-wide prerequisite.'),
 ('prusa-xl-de',17):(VISUAL,'Eleven Multi-Tool entries and photo-local dual-head note retained; source model-count distinction remains local to the photograph.'),
 ('prusa-xl-de',18):(VISUAL,'Ten Multi-Tool entries and literal manual-unlocking note are retained. Exact physical latch targets remain unavailable; no generated unlocking instructions added.'),
 ('prusa-xl-de',46):(VISUAL,'Fourteen interface explanations are retained; raster UI positions unavailable.'),
 ('prusa-xl-de',62):(CORRECTED,'Literal pros/cons columns interleaved, obscuring temperature qualifier and polarity. Recovered by native coordinates; original PLA temperatures and separate marketing note retained.'),
 ('prusa-xl-de',81):(UNRESOLVED,'Product matrix corrected, including dimensions and ingress-protection qualifier. Electrical legend text survives, but symbol associations/electrical interpretation require a qualified human. No electrical-use admission asserted.'),
}

B_NOTES={
 ('prusa-mk4s-en',10):(VISUAL,'Independent introductory prose; photograph is illustrative. No technical parameters are taken from the image.'),
 ('prusa-mk4s-en',35):(VISUAL,'Nozzle sizes, step increment, menu path and adapter conditions are stated in prose. Photograph is supplementary; installation geometry is not reconstructed.'),
 ('prusa-mmu3-en',11):(VISUAL,'Nine source component descriptions independently state functions. Arrow-to-hardware positions remain unavailable.'),
 ('prusa-mmu3-en',41):(VISUAL,'Wipe options, object-height branches and final-filament behavior are explicit in prose. Screenshot/photo details remain unavailable.'),
 ('prusa-mk4-de',33):(UNRESOLVED,'Factory-reset screenshot carries a safety-relevant confirmation qualifier absent from prose. Example-model text is usable; complete reset-procedure support must remain unavailable pending manual review.'),
 ('prusa-mk4-de',50):(VISUAL,'Five steps and subsequent printer-pause instruction retained. Screenshot is a visual supplement; exact UI positions are unavailable.'),
 ('prusa-xl-de',35):(UNRESOLVED,'Factory-reset screenshot adds a safety-relevant confirmation qualifier absent from prose. Do not treat the retained reset paragraph as a complete text-only procedure.'),
 ('prusa-xl-de',83):(VISUAL,'Five source component names retained. PDU physical terminal/connection geometry is essential for spatial identification and remains unavailable; electrical-use interpretation still requires a qualified human.'),
 ('prusa-mini-pl',16):(VISUAL,'Knob action and reset behavior/location are explicitly described in prose. Image-only UI readings/positions remain unavailable.'),
 ('prusa-mini-pl',29):(VISUAL,'Source websites, slicing requirement and software prose are independent of illustrative website screenshot. Publisher URL spelling retained without correction.'),
 ('prusa-mk3s-pl',50):(VISUAL,'Source model-download prose and layer-height caption retained. Photograph adds unavailable appearance, not invented specifications.'),
 ('prusa-mk3s-pl',52):(VISUAL,'Caption explicitly gives left/right distinction. Surface appearance comparison exists only in the photograph and is unavailable; no appearance criteria fabricated.'),
}

C_NOTES={
 ('prusa-mk3s-pl',35):(VERIFIED,'Shared note applies to unlisted menu settings within 7.2.9; print-only conditions stay on their original branches and continuation reaches page 36.'),
 ('prusa-mk3s-pl',36):A_NOTES['prusa-mk3s-pl',36],
 ('prusa-xl-de',23):(VERIFIED,'Warning, cleanliness/no-direct-bed and local finger-clearance scopes checked against source. Alignment prose survives; orange spatial targets remain unavailable.'),
 ('prusa-xl-de',24):(VERIFIED,'Alignment warning continues 4.3, then cleaning instruction follows. Source warning is retained once, not broadcast to every chunk.'),
 ('prusa-mk4s-en',18):(VERIFIED,'Bed-installed prerequisite spans initial wizard and running selftest. Optional internet setup is not a compulsory prerequisite; diagnostic-purpose note is informational.'),
 ('prusa-mk4s-en',19):(UNRESOLVED,'No-touch/stability restriction and minimum filament length are valid source text. Screenshot-only startup state prevents treating filament-sensor calibration as a complete text-only procedure.'),
 ('prusa-mk4-de',21):(VERIFIED,'Bed-installed condition continues to selftest; cleanliness, no-direct-bed and handling restrictions stay with sheet installation, not every later chapter.'),
 ('prusa-mk4-de',22):(UNRESOLVED,'Local no-touch/stability and minimum filament length retained. Screenshot-only sensor-test startup state requires manual availability disposition; no instruction inferred from pixels.'),
 ('prusa-mini-pl',42):(CORRECTED,'Incidental flex pros/cons interleaving outside reviewed 9.1 was observed and corrected from native columns. Section 9.1 cleaning sentence continues onto page 43 without lost words.'),
 ('prusa-mini-pl',43):(VERIFIED,'Continuation retains cool-bed/burn restriction, hygiene condition and reference to material-specific separation layers. No duty to recalibrate after every cleaning is invented.'),
 ('prusa-mini-pl',44):(VERIFIED,'Three source product rows and usage/risk columns checked. Calibration note is conditional on plate changes; warranty is not a procedural prerequisite; hygiene note has its own scope.'),
 ('prusa-mini-pl',45):(UNRESOLVED,'9.1 caption/photos retain source text. Incidental 9.2 column interleaving corrected, but columns lack literal polarity headings; interpretation remains pending instead of inventing them.'),
 ('prusa-mmu3-en',22):(VERIFIED,'Two separate six-step sequences verified. Straight filament-end note belongs to ejection 2.6, not loading 2.5; nozzle-loaded unloading prerequisite and product-specific menu routes retained.'),
}

GROUP_SCOPES={
 'mk3s-menu':'The source note concerns unlisted settings in 7.2.9, including the continued tree on page 36; original print-only branches remain conditional.',
 'xl-sheet':'Bed clearance and no-sliding apply to sheet installation; page-24 alignment warning continues 4.3; bold cleanliness/no-direct-bed restriction applies before placing sheet; finger clearance is local to the alignment paragraph.',
 'mk4s-calibration':'Installed sheet applies before calibration, including running selftest; local no-touch/stability applies while selftest runs; filament-length text applies to selftest/sensor calibration. Optional network setup and purpose note are not mandatory steps.',
 'mk4-calibration':'Installed sheet applies before calibration; sheet cleaning/handling restrictions apply to 4.3; local stability/no-touch and filament prerequisite apply to 4.4. Do not propagate to 4.5 or unrelated chapters.',
 'mini-sheets':'Cleaning requires cool surface and source material-specific handling. Recalibration/Live Z note is conditional on changing plates, not every cleaning. Warranty and double-sided property are not safety prerequisites.',
 'mmu-procedures':'Source 2.5 loading and 2.6 ejection remain distinct; straight-end note belongs to 2.6. Nozzle-loaded unloading condition and printer-specific menu paths retain their literal branches.',
}
