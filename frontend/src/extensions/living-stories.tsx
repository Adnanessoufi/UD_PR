import StoryRoom from '../components/StoryRoom'
import type { FeatureExtension } from './types'

export const livingStories: FeatureExtension = {
  id: 'living-stories',
  slot: 'review.top',
  canRender: (context) => Boolean(context.runId && context.combined),
  Component: ({ context }) =>
    context.runId && context.combined ? (
      <StoryRoom
        runId={context.runId}
        story={context.combined.content}
        language={context.language}
      />
    ) : null,
}
