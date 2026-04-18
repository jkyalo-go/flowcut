/**
 * Small brand-mark component for integrations UI.
 *
 * Looks up an SVG in /public/logos/. Falls back to a subtle text monogram
 * when the slug isn't known, so we never ship a broken-image icon.
 */

const PLATFORM_LOGOS: Record<string, string> = {
  youtube: '/logos/youtube.svg',
  tiktok: '/logos/tiktok.svg',
  instagram: '/logos/instagram.svg',
  instagram_reels: '/logos/instagram.svg',
  linkedin: '/logos/linkedin.svg',
  x: '/logos/x.svg',
  twitter: '/logos/x.svg',
}

const PROVIDER_LOGOS: Record<string, string> = {
  anthropic: '/logos/anthropic.svg',
  openai: '/logos/openai.svg',
  vertex: '/logos/googlecloud.svg',
  gemini: '/logos/googlecloud.svg',
  google: '/logos/googlecloud.svg',
}

const LOGOS: Record<string, string> = { ...PLATFORM_LOGOS, ...PROVIDER_LOGOS }

interface BrandLogoProps {
  slug: string
  label?: string
  size?: number
  className?: string
}

export function BrandLogo({ slug, label, size = 24, className }: BrandLogoProps) {
  const src = LOGOS[slug.toLowerCase()]
  const alt = label ? `${label} logo` : `${slug} logo`
  if (src) {
    // Use plain <img> so the /public/logos SVGs render without next/image config
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={alt}
        width={size}
        height={size}
        className={className}
        style={{ objectFit: 'contain' }}
      />
    )
  }
  const initials = (label ?? slug).slice(0, 2).toUpperCase()
  return (
    <span
      aria-label={alt}
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        borderRadius: 6,
        background: 'rgba(127,127,127,0.15)',
        fontSize: size * 0.42,
        fontWeight: 600,
        color: 'var(--foreground, currentColor)',
      }}
    >
      {initials}
    </span>
  )
}
