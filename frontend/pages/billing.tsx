import { useEffect } from 'react'
import { useRouter } from 'next/router'
import type { GetServerSideProps } from 'next'

export default function BillingPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace('/workspace?tab=plan')
  }, [router])

  return null
}

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: {
    destination: '/workspace?tab=plan',
    permanent: false,
  },
})
