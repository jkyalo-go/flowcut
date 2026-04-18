import { useEffect } from 'react'
import { useRouter } from 'next/router'
import type { GetServerSideProps } from 'next'

export default function AdminPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace('/workspace?tab=admin')
  }, [router])

  return null
}

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: {
    destination: '/workspace?tab=admin',
    permanent: false,
  },
})
