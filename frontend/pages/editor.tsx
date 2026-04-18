import { useEffect } from 'react'
import { useRouter } from 'next/router'
import type { GetServerSideProps } from 'next'

export default function EditorRedirectPage() {
  const router = useRouter()
  const projectId = typeof router.query.project_id === 'string' ? router.query.project_id : null

  useEffect(() => {
    if (!router.isReady) return
    if (projectId) {
      router.replace(`/projects/${projectId}`)
      return
    }
    router.replace('/projects')
  }, [projectId, router])

  return null
}

export const getServerSideProps: GetServerSideProps = async (context) => {
  const projectId = typeof context.query.project_id === 'string' ? context.query.project_id : null
  return {
    redirect: {
      destination: projectId ? `/projects/${projectId}` : '/projects',
      permanent: false,
    },
  }
}
