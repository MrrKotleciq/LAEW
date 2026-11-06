param(
    [ValidateSet('start', 'stop', 'update', 'status', 'logs', 'test')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
$ComposeFile = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../docker-compose.yml')).Path
$CacheVolume = 'laew-horizon_horizon-model-cache'
$BaseUrl = 'http://127.0.0.1:8082'
$Service = 'horizon-sufficiency'
$Model = 'Horizon-Labs/multilingual-zeroshot-small'
$Contract = 'horizon-nli-v1'
$RestOptions = @{ TimeoutSec = 3 }
if ($PSVersionTable.PSVersion.Major -ge 7) { $RestOptions.NoProxy = $true }

function Invoke-Compose([string[]]$ComposeArgs) {
    docker compose --project-name laew --file $ComposeFile @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Horizon Compose failed ($LASTEXITCODE). Inspect .\start-horizon.ps1 logs."
    }
}

function Get-HorizonReadiness {
    $response = Invoke-RestMethod -Uri "$BaseUrl/readyz" @RestOptions
    if ($response.ready -isnot [bool] -or -not $response.ready -or $response.contract -cne $Contract -or
        $response.model_id -cne $Model -or $response.provider -cne 'CPUExecutionProvider') {
        throw 'Unexpected Horizon model, contract, or execution provider.'
    }
    $response
}

function Start-Horizon([switch]$Recreate) {
    # Docker reuses an existing named volume. On a fresh host this provisions the cache.
    docker volume create $CacheVolume | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Cannot provision Horizon cache volume $CacheVolume." }

    $upArgs = @('up', '-d', '--no-deps', '--wait', '--wait-timeout', '450')
    if ($Recreate) { $upArgs += '--force-recreate' }
    Invoke-Compose ($upArgs + $Service)
    Get-HorizonReadiness | Format-List
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI not found. Start Docker Desktop first.'
}

switch ($Action) {
    'start' { Start-Horizon }
    'update' {
        Invoke-Compose @('build', '--pull', $Service)
        Start-Horizon -Recreate
    }
    'stop' { Invoke-Compose @('stop', $Service) }
    'status' {
        Invoke-Compose @('ps', '-a', $Service)
        try { Get-HorizonReadiness | Format-List }
        catch { Write-Warning "Not ready. $($_.Exception.Message)" }
    }
    'logs' { Invoke-Compose @('logs', '-f', '--tail', '100', $Service) }
    'test' {
        Get-HorizonReadiness | Format-List
        $scores = foreach ($premise in @('I visited Sapporo.', 'I planned to visit Sapporo but cancelled the trip.')) {
            $body = @{ premise = $premise; hypothesis = 'I visited Sapporo.' } | ConvertTo-Json
            $result = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/nli" -ContentType 'application/json' -Body $body @RestOptions
            if ($result.contract -cne $Contract -or $result.model_id -cne $Model -or
                $null -eq $result.entailment_score -or $null -eq $result.not_entailment_score -or
                $result.entailment_score -lt 0 -or $result.entailment_score -gt 1 -or
                $result.not_entailment_score -lt 0 -or $result.not_entailment_score -gt 1 -or
                [Math]::Abs($result.entailment_score + $result.not_entailment_score - 1) -gt 0.00001) {
                throw 'Invalid Horizon inference response.'
            }
            $result
        }
        if ($scores[0].entailment_score -le 0.8 -or $scores[1].entailment_score -ge 0.5) {
            throw 'Horizon did not distinguish the supported and unsupported visit claims.'
        }
        $scores | Format-List
    }
}
