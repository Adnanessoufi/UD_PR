import { Component, type ReactNode } from 'react'
import { extensions } from './index'
import type { ExtensionContext, ExtensionSlotName, FeatureExtension } from './types'

class ExtensionBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    if (this.state.failed)
      return (
        <section className="workspace-media-progress" role="alert">
          <p>This tool could not load.</p>
          <button
            type="button"
            className="ud-secondary-button"
            onClick={() => this.setState({ failed: false })}
          >
            Try again
          </button>
        </section>
      )
    return this.props.children
  }
}

function VisibleFeature({
  feature,
  context,
}: {
  feature: FeatureExtension
  context: ExtensionContext
}) {
  const Feature = feature.Component
  return !feature.canRender || feature.canRender(context) ? <Feature context={context} /> : null
}

export default function ExtensionSlot({
  name,
  context,
}: {
  name: ExtensionSlotName
  context: ExtensionContext
}) {
  return (
    <>
      {extensions
        .filter((feature) => feature.slot === name)
        .map((feature) => {
          return (
            <ExtensionBoundary key={`${feature.id}:${context.runId}:${context.language}`}>
              <VisibleFeature feature={feature} context={context} />
            </ExtensionBoundary>
          )
        })}
    </>
  )
}
