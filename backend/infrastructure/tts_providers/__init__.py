"""TTS provider package.

Import concrete providers from their modules to avoid loading optional audio
dependencies for tests that only need the OpenAI-compatible speech provider.
"""
