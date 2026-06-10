'use client'

import { notFound } from 'next/navigation'
import SectionOpener from '@/components/browse/SectionOpener'
import { categories } from '@/lib/categoryConfig'

export default function CategoryPage({ params }: { params: { category: string } }) {
  const category = categories.find((c) => c.slug === params.category)
  if (!category) return notFound()

  return <SectionOpener category={category} />
}
