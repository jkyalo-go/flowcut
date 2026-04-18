import Link from 'next/link'
import { useRouter } from 'next/router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function BillingSuccessPage() {
  const router = useRouter()
  const sessionId = typeof router.query.session_id === 'string' ? router.query.session_id : null

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <Card>
        <CardHeader>
          <p className="eyebrow">Billing</p>
          <CardTitle className="text-2xl">Checkout complete</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The billing handoff completed and the workspace can refresh its subscription state now.
          </p>
          {sessionId && (
            <p className="text-xs text-muted-foreground">Stripe session: {sessionId}</p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/workspace?tab=plan">Return to plan settings</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/">Open overview</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
