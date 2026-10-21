import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/demo/samples.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext },
}).outputText
const { samples, channels, sampleDraft } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

test('every sample excerpt is present verbatim in its own language source', () => {
  for (const sample of samples)
    for (const language of ['en', 'hu']) {
      const text = sample[language]
      for (const fact of text.facts)
        assert.ok(text.source.includes(fact.excerpt), `${sample.id}/${language}/${fact.id}`)
      for (const question of text.questions)
        assert.ok(text.facts.some((fact) => fact.id === question.factId))
    }
})

test('all channels have bilingual drafts and the fictional source remains labelled', () => {
  assert.equal(samples.length, 2)
  assert.equal(channels.length, 6)
  for (const sample of samples)
    for (const language of ['en', 'hu']) {
      assert.match(
        sample[language].source,
        language === 'en' ? /FICTIONAL SOURCE/ : /KITALÁLT FORRÁS/,
      )
      for (const channel of channels) {
        const draft = sampleDraft(sample, language, channel.id)
        assert.ok(draft.title.trim())
        assert.ok(draft.body.trim())
      }
    }
  assert.match(samples[0].en.article.body, /no control group/)
  assert.match(samples[1].en.article.body, /no real event/)
})

test('Vercel builds the static demo and publishes only frontend dist', () => {
  const config = JSON.parse(readFileSync(new URL('../../vercel.json', import.meta.url), 'utf8'))
  assert.equal(config.outputDirectory, 'frontend/dist')
  assert.match(config.buildCommand, /build:demo/)
  const env = readFileSync(new URL('../.env.demo', import.meta.url), 'utf8')
  assert.match(env, /^VITE_DEMO_MODE=true$/m)
  assert.doesNotMatch(env, /API_KEY=/)
})

test('every campaign ships its poster, playable MP4 container and captions', () => {
  for (const sample of samples) {
    const base = new URL('../public/', import.meta.url)
    assert.match(readFileSync(new URL(sample.image.slice(1), base), 'utf8'), /FICTIONAL SAMPLE/)
    const video = readFileSync(new URL(sample.video.slice(1), base))
    assert.equal(video.subarray(4, 8).toString(), 'ftyp')
    const captions = readFileSync(new URL(`demo/${sample.id}.vtt`, base), 'utf8')
    assert.match(captions, /^WEBVTT/)
    assert.equal((captions.match(/ --> /g) || []).length, 3)
  }
})
