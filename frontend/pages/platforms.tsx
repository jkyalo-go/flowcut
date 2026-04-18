import { useEffect } from 'react'
import { useRouter } from 'next/router'
import type { GetServerSideProps } from 'next'

export default function PlatformsPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace('/integrations?tab=platforms')
  }, [router])

  return null
}

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: {
    destination: '/integrations?tab=platforms',
    permanent: false,
  },
})
