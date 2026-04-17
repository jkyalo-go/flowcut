import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api'

interface Summary { total_workspaces: number; active_jobs: number; [key: string]: unknown }
interface Job { id: string; job_type: string; status: string; created_at: string }
interface ActionLog { id: string; action: string; actor: string; created_at: string }
interface ComplianceExport { id: string; status: string; created_at: string; download_url?: string }
interface Onboarding { workspace_id: string; checklist_json: string }

interface ChecklistStep {
  label: string
  completed: boolean
}

function jobStatusVariant(status: string): 'default' | 'destructive' | 'secondary' {
  if (status === 'running') return 'default'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

export function AdminPage() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [actions, setActions] = useState<ActionLog[]>([])
  const [exports, setExports] = useState<ComplianceExport[]>([])
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [creatingExport, setCreatingExport] = useState(false)

  useEffect(() => {
    let mounted = true
    Promise.all([
      api.get<Summary>('/api/enterprise/admin/summary').catch(() => null),
      api.get<Job[]>('/api/enterprise/admin/jobs').catch(() => []),
      api.get<ActionLog[]>('/api/enterprise/admin/actions').catch(() => []),
      api.get<ComplianceExport[]>('/api/enterprise/compliance-exports').catch(() => []),
      api.get<Onboarding>('/api/enterprise/onboarding').catch(() => null),
    ]).then(([summaryData, jobsData, actionsData, exportsData, onboardingData]) => {
      if (mounted) {
        setSummary(summaryData)
        setJobs(jobsData ?? [])
        setActions(actionsData ?? [])
        setExports(exportsData ?? [])
        setOnboarding(onboardingData)
        setLoading(false)
      }
    })
    return () => { mounted = false }
  }, [])

  async function createExport() {
    setError('')
    setCreatingExport(true)
    try {
      const newExport = await api.post<ComplianceExport>('/api/enterprise/compliance-exports', { format: 'json' })
      setExports((prev) => [newExport, ...prev])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create compliance export')
    } finally {
      setCreatingExport(false)
    }
  }

  let checklist: ChecklistStep[] = []
  if (onboarding) {
    try {
      checklist = JSON.parse(onboarding.checklist_json) as ChecklistStep[]
    } catch (_err) {
      checklist = []
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Admin</h1>
        <p className="text-sm text-muted-foreground">Enterprise administration dashboard.</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <div className="space-y-6">
          {/* Summary stats */}
          {summary !== null && (
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardContent className="pt-4">
                  <p className="text-2xl font-bold">{summary.total_workspaces}</p>
                  <p className="text-xs text-muted-foreground">Total workspaces</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <p className="text-2xl font-bold">{summary.active_jobs}</p>
                  <p className="text-xs text-muted-foreground">Active jobs</p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Onboarding checklist */}
          {onboarding !== null && checklist.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Onboarding checklist</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {checklist.map((step, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <span>{step.completed ? '✅' : '⬜'}</span>
                      <span>{step.label}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Tabs */}
          <Tabs defaultValue="jobs">
            <TabsList>
              <TabsTrigger value="jobs">Background jobs</TabsTrigger>
              <TabsTrigger value="actions">Action log</TabsTrigger>
              <TabsTrigger value="exports">Compliance exports</TabsTrigger>
            </TabsList>

            {/* Background jobs tab */}
            <TabsContent value="jobs">
              <Card>
                <CardHeader>
                  <CardTitle>Background jobs</CardTitle>
                </CardHeader>
                <CardContent>
                  {jobs.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No jobs found.</p>
                  ) : (
                    <div className="divide-y">
                      {jobs.map((job) => (
                        <div key={job.id} className="flex items-center justify-between py-3">
                          <div className="space-y-0.5">
                            <p className="text-sm font-medium">{job.job_type}</p>
                            <p className="text-xs text-muted-foreground">
                              {new Date(job.created_at).toLocaleString()}
                            </p>
                          </div>
                          <Badge variant={jobStatusVariant(job.status)}>
                            {job.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Action log tab */}
            <TabsContent value="actions">
              <Card>
                <CardHeader>
                  <CardTitle>Action log</CardTitle>
                </CardHeader>
                <CardContent>
                  {actions.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No actions recorded.</p>
                  ) : (
                    <div className="divide-y">
                      {actions.map((log) => (
                        <div key={log.id} className="flex items-start justify-between py-3">
                          <div className="space-y-0.5">
                            <p className="text-sm font-medium">{log.action}</p>
                            <p className="text-xs text-muted-foreground">{log.actor}</p>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {new Date(log.created_at).toLocaleString()}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Compliance exports tab */}
            <TabsContent value="exports">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Compliance exports</CardTitle>
                    <Button
                      size="sm"
                      onClick={createExport}
                      disabled={creatingExport}
                    >
                      {creatingExport ? 'Creating...' : 'New compliance export'}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {exports.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No exports yet.</p>
                  ) : (
                    <div className="divide-y">
                      {exports.map((exp) => (
                        <div key={exp.id} className="flex items-center justify-between py-3">
                          <div className="space-y-0.5">
                            <Badge variant={exp.status === 'failed' ? 'destructive' : exp.status === 'complete' ? 'default' : 'secondary'}>
                              {exp.status}
                            </Badge>
                            <p className="text-xs text-muted-foreground">
                              {new Date(exp.created_at).toLocaleString()}
                            </p>
                          </div>
                          {exp.download_url && (
                            <a
                              href={exp.download_url}
                              className="text-xs text-blue-600 hover:underline"
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              Download
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  )
}
