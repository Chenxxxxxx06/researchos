# ResearchOS API Smoke Test (PowerShell)
# Runs against http://localhost:8000 with the demo account.
param($BaseUrl = "http://localhost:8000")

$ErrorActionPreference = "Stop"
$demoEmail = "demo@researchos.dev"
$demoPassword = "demo-password-123"
$passed = 0; $failed = 0

function Assert($label, $script) {
    try { & $script; Write-Host "  PASS $label" -Fore Green; $global:passed++ }
    catch { Write-Host "  FAIL $label : $_" -Fore Red; $global:failed++ }
}

Write-Host "=== ResearchOS API Smoke ===" -Fore Cyan

# --- Health ---
Assert "healthz" { $r = Invoke-RestMethod "$BaseUrl/healthz"; if ($r.status -ne "ok") { throw "bad status" } }
Assert "readyz"  { $r = Invoke-RestMethod "$BaseUrl/readyz"; if ($r.status -ne "ok") { throw "down" } }

# --- Auth: login + get current user ---
$login = Invoke-RestMethod -Uri "$BaseUrl/auth/login" -Method Post -ContentType "application/json" -Body "{`"email`":`"$demoEmail`",`"password`":`"$demoPassword`"}" -SessionVariable sess
Assert "login" { if (-not $login.id) { throw "no user id" } }

$me = Invoke-RestMethod -Uri "$BaseUrl/auth/me" -WebSession $sess
Assert "me"   { if ($me.user.email -ne $demoEmail) { throw "wrong user" } }

# --- Organizations + Projects ---
$orgs = Invoke-RestMethod -Uri "$BaseUrl/organizations" -WebSession $sess
$orgId = $orgs[0].id
Assert "orgs"  { if (-not $orgId) { throw "no org" } }

$projPage = Invoke-RestMethod -Uri "$BaseUrl/projects?organization_id=$orgId" -WebSession $sess
$projId = $projPage.items[0].id
Assert "projects" { if (-not $projId) { throw "no project" } }
Write-Host "  INFO projectId=$projId" -Fore Gray

# --- Research ---
$papers = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/papers" -WebSession $sess
Assert "papers" { if ($papers.total -lt 1) { throw "no papers" } }

$ideas = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/ideas" -WebSession $sess
Assert "ideas"  { if ($ideas.total -lt 1) { throw "no ideas" } }

# --- IDE Workspace ---
$tree = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/workspace/tree" -WebSession $sess
Assert "workspace tree" { if ($tree.nodes.Count -lt 1) { throw "empty tree" } }

# --- Experiments ---
$exps = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/experiments" -WebSession $sess
Assert "experiments" { if ($exps.Count -lt 2) { throw "need 2 experiments" } }
$expId = $exps[0].id
$runs = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/experiments/$expId/runs" -WebSession $sess
Assert "runs" { if ($runs.Count -lt 1) { throw "no runs" } }

# --- Paper (LaTeX) ---
$latexProjects = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/latex-projects" -WebSession $sess
Assert "latex projects" { if ($latexProjects.Count -lt 1) { throw "no latex project" } }

# --- Skills ---
$catalog = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/skills/catalog" -WebSession $sess
Assert "skills catalog" { if ($catalog.Count -lt 3) { throw "need 3+ skills" } }

$installed = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/skills/installed" -WebSession $sess
Assert "skills installed" { if ($installed.Count -lt 1) { throw "no installed skills" } }

# --- Settings / LLM ---
$llmConfigs = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/settings/llm" -WebSession $sess
Assert "llm configs" { if (-not $llmConfigs) { throw "empty config list" } }

# --- Git ---
$git = Invoke-RestMethod -Uri "$BaseUrl/projects/$projId/git/status" -WebSession $sess
Assert "git status" { if (-not $git.branch) { throw "no branch" } }

Write-Host "=== Result: $passed passed, $failed failed ===" -Fore $(if ($failed -eq 0) { "Green" } else { "Red" })
exit $failed
