param(
    [string]$Path = (Join-Path $PSScriptRoot '..\src\hits.htm'),
    [int]$MaxPhotos = 2,
    [int]$Limit = 0
)

$ErrorActionPreference = 'Stop'
$Path = (Resolve-Path $Path).Path
$bytes = [IO.File]::ReadAllBytes($Path)
$hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
$encoding = New-Object System.Text.UTF8Encoding($hasBom)
$lines = [IO.File]::ReadAllText($Path, $encoding) -split "`n"
$headers = @{ 'User-Agent' = 'belarus-districts-game-photo-fill/1.0 (educational project)' }
$report = New-Object System.Collections.Generic.List[string]

function Get-CommonsPhotos([string]$query) {
    $q = [uri]::EscapeDataString($query)
    $url = "https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch=$q&gsrlimit=10&prop=imageinfo&iiprop=url&iiurlwidth=1024&format=json&formatversion=2"
    $response = $null

    for ($attempt = 1; $attempt -le 3 -and -not $response; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 30
        }
        catch {
            if ($attempt -eq 3) {
                $script:report.Add("ERROR: $query - $($_.Exception.Message)")
                return @()
            }
            Start-Sleep -Seconds (20 * $attempt)
        }
    }

    if (-not $response.query -or -not $response.query.pages) { return @() }

    $result = @()
    foreach ($page in @($response.query.pages | Sort-Object { $_.index })) {
        $info = $page.imageinfo | Select-Object -First 1
        if ($info -and $page.title -match '\.(jpe?g|png)$') {
            $result += [pscustomobject]@{ Title = $page.title; Url = $info.thumburl }
        }
        if ($result.Count -ge $MaxPhotos) { break }
    }
    return $result
}

function Get-SearchQuery([string]$name, [string]$district) {
    $query = $name -replace '\s+в\s+д\.\s*', ' '
    if ($query -ne $name) {
        return ($query -replace '\s+', ' ').Trim()
    }

    return "$name $district"
}

$targets = New-Object System.Collections.Generic.List[object]
$district = $null
$item = $null
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*"name": "(.+)",\s*$') {
        $name = ('"' + $Matches[1] + '"' | ConvertFrom-Json)
        $isDistrict = $i + 1 -lt $lines.Count -and $lines[$i + 1] -match '^\s*"items"'
        if ($isDistrict) { $district = $name } else { $item = $name }
    }
    elseif ($lines[$i] -match '^\s*"photos": \[\]' -and $item) {
        $targets.Add([pscustomobject]@{ Index = $i; Name = $item; District = $district })
    }
}

if ($Limit -gt 0) { $targets = @($targets | Select-Object -First $Limit) }
Write-Host "Objects without photos: $($targets.Count)"

$reportPath = Join-Path $PSScriptRoot 'photo-report.txt'
[IO.File]::WriteAllLines($reportPath, $report, $encoding)

$filled = 0
foreach ($t in $targets) {
    $query = Get-SearchQuery $t.Name $t.District
    $found = @(Get-CommonsPhotos $query)
    Start-Sleep -Milliseconds 1500

    if ($found.Count -eq 0) {
        $report.Add("NOT FOUND: $query")
        Write-Host "NOT FOUND: $query"
        [IO.File]::WriteAllLines($reportPath, $report, $encoding)
        continue
    }

    $line = $lines[$t.Index]
    $cr = if ($line.EndsWith("`r")) { "`r" } else { '' }
    $indent = $line -replace '"photos".*$', ''
    $items = ($found | ForEach-Object { '"' + $_.Url + '"' }) -join ', '
    $lines[$t.Index] = $indent + '"photos": [' + $items + ']' + $cr
    $filled++
    $report.Add("OK: $query")
    foreach ($f in $found) { $report.Add("    [$($f.Title)] $($f.Url)") }
    [IO.File]::WriteAllText($Path, ($lines -join "`n"), $encoding)
    [IO.File]::WriteAllLines($reportPath, $report, $encoding)
    Write-Host "[$filled] $query -> $($found.Count) photo(s)"
}

[IO.File]::WriteAllText($Path, ($lines -join "`n"), $encoding)
[IO.File]::WriteAllLines($reportPath, $report, $encoding)
Write-Host "Filled: $filled of $($targets.Count)"
Write-Host "Report: $reportPath"
