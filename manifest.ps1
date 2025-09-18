$buildDate = Get-Date -Format "yyyy-MM-dd"
$semVersion = "1.0.0"

$gitSha = (git rev-parse HEAD).Trim()
$gitBranch = (git rev-parse --abbrev-ref HEAD).Trim()
$gitRepo = (git config --get remote.origin.url).Trim()
$gitUrl = ($gitRepo -replace '\.git$', '') -replace '^git@', 'https://'
$gitUrl = $gitUrl -replace '.com:', '.com/'

#create a hashtable to hold the metadata
$metadata = @{
    'build_date' = $buildDate
    'version' = $semVersion
    'git_sha' = $gitSha
    'git_branch' = $gitBranch
    'git_repo' = $gitRepo
    'git_url' = $gitUrl
    'author' = "Dan Luca"
    'description' = "Smart garden watering management system"
    'name' = "Waterly"
    'license' = "MIT"
}
#convert the hashtable to JSON
$metadataJson = $metadata | ConvertTo-Json -Depth 3
#write the JSON to a file
$manifestPath = Join-Path $PSScriptRoot "src/web/static/manifest.json"
$metadataJson | Out-File -FilePath $manifestPath -Encoding utf8
Copy-Item $manifestPath $PSScriptRoot/frontend/public/api/manifest -Force
