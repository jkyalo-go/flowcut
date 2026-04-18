import { useEffect } from 'react'
import { useRouter } from 'next/router'
import type { GetServerSideProps } from 'next'

export default function AISettingsPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace('/integrations?tab=ai')
  }, [router])

  return null
}

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: {
    destination: '/integrations?tab=ai',
    permanent: false,
  },
})
