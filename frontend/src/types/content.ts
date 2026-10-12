export type SourceFact = {
  id: string
  statement: string
  category: string
  page: number | null
  source_excerpt: string
  importance: 'high' | 'medium' | 'low'
}

export type SourceAnalysis = {
  document_type: string
  source_language: string
  title: string
  organization: string
  people: string[]
  summary: string
  key_facts: SourceFact[]
  important_numbers: string[]
  important_dates: string[]
  conditions_and_limitations: string[]
  communication_focus: string
  source_links?: string[]
  research_sources?: {
    title: string
    url: string
    domain: string
    source_type: 'official' | 'secondary'
  }[]
  warning?: string | null
}

export type MasterContent = {
  headline: string
  lead: string
  body: string
  short_summary: string
  key_messages: string[]
  press_release: string
  source_fact_ids: string[]
}

export type CombinedResult = {
  analysis: SourceAnalysis
  content: MasterContent
  output_language: 'en' | 'hu'
}
