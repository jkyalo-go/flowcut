import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function BillingCancelPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <Card>
        <CardHeader>
          <p className="eyebrow">Billing</p>
          <CardTitle className="text-2xl">Checkout cancelled</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            No billing change was applied. You can return to the plan screen and retry when ready.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/workspace?tab=plan">Back to plan settings</Link>
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
