# CaseNote: 2-minute demo voiceover

Target: 1:55, about 270 words at a calm pace (~140 words per minute).
Read the **Voiceover** column; the **Screen** column is what the edit shows at that moment.

| Time | Screen | Voiceover |
|---|---|---|
| 0:00 to 0:12 | Black title card: "14 hours. No WiFi. One expired signature." Then the Mac menu bar with WiFi turned off. | Two hours before landing, an international student realises she has no idea if her papers are in order. There's no internet on the plane, and she's not uploading her passport to a random website anyway. |
| 0:12 to 0:20 | CaseNote empty state, verdict "Check your documents before you fly." | This is CaseNote. It recreates an AI immigration assistant, but everything runs on this Mac with WiFi off. |
| 0:20 to 0:42 | Click "Use sample documents". Passport and visa finish instantly; I-20 and I-94 read. (Speed up the wait 4x and label it.) | She adds her passport, visa, I-20 and I-94. Apple Vision reads the text. The passport and visa are verified with their machine-readable check digits, and PrismML's Bonsai 9B reads the I-20 and I-94 into fields. |
| 0:42 to 1:00 | Verdict turns red: "2 things to fix before you re-enter." Click the I-94 finding; the sheet highlights the swapped names. | Then CaseNote cross-checks everything against seven official DHS, ICE and CBP rules. It found two problems: her travel signature is fourteen months old, and her I-94 has her surname and given name swapped. Every finding points to the exact spot on the document and links to the rule. |
| 1:00 to 1:25 | Tap the mic, ask in Chinese. Transcript appears, then the cited answer; the answer is read aloud. | She asks in Chinese. Argmax WhisperKit transcribes it on-device, Bonsai answers only from her documents and the rules, with citations, and Argmax TTSKit reads it back. |
| 1:25 to 1:40 | Deadlines list, then "Add to Calendar". | CaseNote also turns her documents into deadlines: when her visa expires, when her OPT window opens, and adds them to her calendar. |
| 1:40 to 1:52 | Attorney meeting: transcript with Speaker 1 and Speaker 2, then the PDF packet. | When she meets a lawyer, Argmax transcribes the meeting and separates the speakers. One click creates an English case packet for the attorney. |
| 1:52 to 2:00 | End card: "CaseNote. Bonsai 9B + Argmax. Zero bytes uploaded." | CaseNote. Your immigration case, checked on your own Mac. |

## Recording tips

- Record the voiceover in a quiet room, phone about 20 cm from your mouth.
- Keep the WiFi-off icon visible in at least one shot; the rules require the app to run with WiFi off.
- Label every sped-up section ("4x") so judges know it's real-time on-device work.
- Sample documents are fictional and marked SPECIMEN; say "sample documents" if asked.
