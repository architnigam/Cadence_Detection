$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$docPath=Join-Path $root 'output/documents/Cadence_Project_and_Team_Guide.docx'
$docPdf=Join-Path $root 'tmp/guide-preview.pdf'
$deckPath=Join-Path $root 'presentation/Cadence_Case_Study_Solution.pptx'
$deckPdf=Join-Path $root 'tmp/deck-preview.pdf'
$word=$null;$document=$null
try {
 $word=New-Object -ComObject Word.Application
 $word.Visible=$false
 $word.DisplayAlerts=0
 $document=$word.Documents.Open($docPath,$false,$true)
 $document.ExportAsFixedFormat($docPdf,17)
 Write-Output "Word preview exported."
} finally {
 if($document){$document.Close($false)}
 if($word){$word.Quit()}
}
$powerpoint=$null;$deck=$null
try {
 $powerpoint=New-Object -ComObject PowerPoint.Application
 $deck=$powerpoint.Presentations.Open($deckPath,$true,$false,$false)
 $deck.SaveAs($deckPdf,32)
 Write-Output "PowerPoint preview exported."
} finally {
 if($deck){$deck.Close()}
 if($powerpoint){$powerpoint.Quit()}
}
