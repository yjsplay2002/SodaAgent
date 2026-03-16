param(
    [string]$ProjectId = $(if ($env:GOOGLE_CLOUD_PROJECT) { $env:GOOGLE_CLOUD_PROJECT } else { "soda-agent-hackathon" }),
    [string]$Region = $(if ($env:GOOGLE_CLOUD_LOCATION) { $env:GOOGLE_CLOUD_LOCATION } else { "us-central1" }),
    [string]$ServiceName = "soda-agent",
    [string]$RepoName = "soda-agent-repo",
    [string]$FirebaseProjectId = "sodaagent",
    [string]$FirebaseStorageBucket = "sodaagent.firebasestorage.app"
)

$ErrorActionPreference = "Stop"
$script:GCloudCli = (Get-Command gcloud.cmd -ErrorAction Stop).Source

function Invoke-GCloud {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$AllowFailure,
        [switch]$Quiet
    )

    $stdoutFile = Join-Path $env:TEMP ("gcloud-stdout-" + [guid]::NewGuid().ToString() + ".log")
    $stderrFile = Join-Path $env:TEMP ("gcloud-stderr-" + [guid]::NewGuid().ToString() + ".log")
    try {
        $process = Start-Process `
            -FilePath $script:GCloudCli `
            -ArgumentList (@($Arguments) + "--access-token-file=$script:TokenFile") `
            -Wait `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $stdoutFile `
            -RedirectStandardError $stderrFile

        $stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw } else { "" }
        $stderr = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { "" }

        if (-not $Quiet) {
            if ($stdout) {
                Write-Host ($stdout.TrimEnd())
            }
            if ($stderr) {
                Write-Host ($stderr.TrimEnd())
            }
        }

        if (-not $AllowFailure -and $process.ExitCode -ne 0) {
            throw "gcloud command failed ($($process.ExitCode)): gcloud $($Arguments -join ' ')"
        }

        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            StdOut = $stdout
            StdErr = $stderr
        }
    } finally {
        if (Test-Path $stdoutFile) {
            Remove-Item $stdoutFile -Force
        }
        if (Test-Path $stderrFile) {
            Remove-Item $stderrFile -Force
        }
    }

    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed: gcloud $($Arguments -join ' ')"
    }
}

function Test-GCloudSecret {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $result = Invoke-GCloud -Arguments @(
        "secrets", "describe", $Name,
        "--project=$ProjectId"
    ) -AllowFailure -Quiet
    return $result.ExitCode -eq 0
}

$firebaseConfigPath = Join-Path $HOME ".config\configstore\firebase-tools.json"
if (-not (Test-Path $firebaseConfigPath)) {
    throw "Firebase CLI login metadata was not found at $firebaseConfigPath."
}

$firebaseConfig = Get-Content $firebaseConfigPath -Raw | ConvertFrom-Json
$accessToken = $firebaseConfig.tokens.access_token
if (-not $accessToken) {
    throw "Firebase CLI access token is missing. Run 'npx firebase-tools login' first."
}

$script:TokenFile = Join-Path $env:TEMP ("gcloud-access-token-" + [guid]::NewGuid().ToString() + ".txt")
Set-Content -Path $script:TokenFile -Value $accessToken -NoNewline

try {
    $image = "$Region-docker.pkg.dev/$ProjectId/$RepoName/$ServiceName"
    $secrets = @(
        "GOOGLE_API_KEY=google-api-key:latest",
        "GOOGLE_MAPS_API_KEY=google-maps-api-key:latest",
        "GOOGLE_OAUTH_CLIENT_ID=google-oauth-client-id:latest",
        "GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest",
        "GOOGLE_OAUTH_REFRESH_TOKEN=google-oauth-refresh-token:latest"
    )

    if (Test-GCloudSecret -Name "naver-maps-api-key-id") {
        $secrets += "NAVER_MAPS_API_KEY_ID=naver-maps-api-key-id:latest"
    }

    if (Test-GCloudSecret -Name "naver-maps-api-key") {
        $secrets += "NAVER_MAPS_API_KEY=naver-maps-api-key:latest"
    }

    Write-Host "=== Deploying SodaAgent to Cloud Run ==="
    Write-Host "Project: $ProjectId"
    Write-Host "Region:  $Region"
    Write-Host ""

    Write-Host "[0/4] Ensuring Artifact Registry repository..."
    $repoResult = Invoke-GCloud -Arguments @(
        "artifacts", "repositories", "describe", $RepoName,
        "--location=$Region",
        "--project=$ProjectId"
    ) -AllowFailure -Quiet
    if ($repoResult.ExitCode -ne 0) {
        Invoke-GCloud -Arguments @(
            "artifacts", "repositories", "create", $RepoName,
            "--repository-format=docker",
            "--location=$Region",
            "--project=$ProjectId"
        )
    }

    Write-Host "[1/4] Building container image..."
    Invoke-GCloud -Arguments @(
        "builds", "submit",
        "--project=$ProjectId",
        "--tag=$image",
        "--timeout=600",
        "."
    )

    Write-Host "[2/4] Deploying to Cloud Run..."
    Invoke-GCloud -Arguments @(
        "run", "deploy", $ServiceName,
        "--project=$ProjectId",
        "--image=$image",
        "--region=$Region",
        "--min-instances=1",
        "--max-instances=3",
        "--memory=1Gi",
        "--cpu=2",
        "--timeout=3600",
        "--session-affinity",
        "--allow-unauthenticated",
        "--set-secrets=$($secrets -join ',')",
        "--set-env-vars=GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=$Region,CALENDAR_TIMEZONE=Asia/Seoul,FIREBASE_PROJECT_ID=$FirebaseProjectId,FIREBASE_STORAGE_BUCKET=$FirebaseStorageBucket"
    )

    Write-Host "[3/4] Getting service URL..."
    $serviceDescribe = Invoke-GCloud -Arguments @(
        "run", "services", "describe", $ServiceName,
        "--project=$ProjectId",
        "--region=$Region",
        "--format=value(status.url)"
    ) -Quiet
    $serviceUrl = $serviceDescribe.StdOut.Trim()
    if (-not $serviceUrl) {
        throw "Unable to read Cloud Run service URL."
    }
    Write-Host "Service URL: $serviceUrl"

    Write-Host "[4/4] Health check..."
    try {
        $healthResponse = Invoke-WebRequest -UseBasicParsing -Uri "$serviceUrl/health" -TimeoutSec 30
        $healthStatus = [int]$healthResponse.StatusCode
    } catch {
        $healthStatus = 0
    }

    if ($healthStatus -eq 200) {
        Write-Host "Health check passed."
    } else {
        Write-Host "Health check returned: $healthStatus. Service may still be starting."
    }

    Write-Host ""
    Write-Host "=== Deployment Complete ==="
    Write-Host "Service URL: $serviceUrl"
    Write-Host "Health:      $serviceUrl/health"
    Write-Host "WebSocket:   $($serviceUrl -replace '^https', 'wss')/ws/mobile?ticket={ticket}"
} finally {
    if (Test-Path $script:TokenFile) {
        Remove-Item $script:TokenFile -Force
    }
}
