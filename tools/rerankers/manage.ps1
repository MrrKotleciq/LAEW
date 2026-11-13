param(
    [Parameter(Mandatory=$true)][ValidateSet('gte', 'bge', 'mxbai')][string]$Model,
    [ValidateSet('start', 'stop', 'status')][string]$Action = 'start'
)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $repository
try {
    $service = "reranker-$Model"
    if ($Action -eq 'start') {
        $port = @{gte=8083; bge=8084; mxbai=8085}[$Model]
        $running = docker ps --filter "label=com.docker.compose.project=laew" --filter "label=com.docker.compose.service=$service" --format '{{.Names}}'
        if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Docker' }
        if (-not $running) {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
            try { $listener.Start() } finally { $listener.Stop() }
        }
        $others = @(docker ps --filter 'label=com.docker.compose.project=laew' --format '{{.Label "com.docker.compose.service"}}' | Where-Object { $_ -like 'reranker-*' -and $_ -ne $service })
        if ($others.Count) { throw "Stop the other reranker first: $($others -join ', '). Sequential operation protects RAM." }
        docker compose --profile $service up -d --no-deps --build $service
    } elseif ($Action -eq 'stop') {
        docker compose --profile $service stop $service
    } else {
        docker compose --profile $service ps -a $service
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker operation failed for $service" }
} finally {
    Pop-Location
}
