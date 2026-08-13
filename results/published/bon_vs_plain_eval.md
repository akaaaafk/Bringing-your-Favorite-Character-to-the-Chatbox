# Best-of-N vs plain LoRA — persona consistency

- Characters: jack, bateman, alvy, ben, erin
- Prompts per character: 8
- BoN candidates (N): 3
- Seed: [42, 43, 44]
- LLM judge: `Qwen/Qwen2.5-1.5B-Instruct (base, LoRA disabled)`
- Pairs: 120

## Aggregate

| Metric | Plain LoRA | Best-of-N | Δ (BoN − plain) |
|---|---:|---:|---:|
| Mean classifier P(target) | 0.2131 | 0.4217 | 0.2086 |
| Mean LLM judge (1–5) | 2.050 | 2.217 | 0.167 |

- Classifier pairwise: BoN wins **96**, plain wins **24**, ties **0**
- Judge pairwise: BoN wins **31**, plain wins **24**, ties **65**

Note: the classifier metric uses the same scorer as the reranker, so BoN is expected to look better on that axis by selection. The LLM judge (base instruct model, LoRA off) is the independent check.

## Per example

| persona | prompt | plain clf | BoN clf | plain judge | BoN judge |
|---|---|---:|---:|---:|---:|
| jack | How's your day going? | 0.334 | 0.758 | 5 | 1 |
| jack | What do you think about modern life? | 0.013 | 0.498 | 5 | 5 |
| jack | Someone just cut me off in traffic. What should  | 0.654 | 0.326 | 5 | 1 |
| jack | Tell me something you care about. | 0.830 | 0.384 | 1 | 1 |
| jack | I'm bored. Entertain me. | 0.876 | 0.543 | 1 | 1 |
| jack | Do you trust people? | 0.923 | 0.414 | 1 | 1 |
| jack | What's the worst advice you've ever gotten? | 0.096 | 0.584 | 5 | 1 |
| jack | Describe yourself in one sentence. | 0.010 | 0.685 | 1 | 5 |
| bateman | How's your day going? | 0.302 | 0.539 | 5 | 1 |
| bateman | What do you think about modern life? | 0.151 | 0.133 | 5 | 5 |
| bateman | Someone just cut me off in traffic. What should  | 0.194 | 0.233 | 1 | 1 |
| bateman | Tell me something you care about. | 0.118 | 0.214 | 1 | 1 |
| bateman | I'm bored. Entertain me. | 0.244 | 0.121 | 1 | 1 |
| bateman | Do you trust people? | 0.179 | 0.206 | 1 | 1 |
| bateman | What's the worst advice you've ever gotten? | 0.040 | 0.213 | 5 | 1 |
| bateman | Describe yourself in one sentence. | 0.434 | 0.260 | 1 | 1 |
| alvy | How's your day going? | 0.074 | 0.978 | 1 | 1 |
| alvy | What do you think about modern life? | 0.020 | 0.397 | 5 | 5 |
| alvy | Someone just cut me off in traffic. What should  | 0.331 | 0.642 | 1 | 5 |
| alvy | Tell me something you care about. | 0.050 | 0.413 | 1 | 5 |
| alvy | I'm bored. Entertain me. | 0.017 | 0.128 | 1 | 1 |
| alvy | Do you trust people? | 0.018 | 0.896 | 3 | 5 |
| alvy | What's the worst advice you've ever gotten? | 0.019 | 0.178 | 1 | 1 |
| alvy | Describe yourself in one sentence. | 0.005 | 0.139 | 5 | 5 |
| ben | How's your day going? | 0.027 | 0.051 | 5 | 3 |
| ben | What do you think about modern life? | 0.035 | 0.084 | 1 | 1 |
| ben | Someone just cut me off in traffic. What should  | 0.026 | 0.204 | 1 | 1 |
| ben | Tell me something you care about. | 0.168 | 0.033 | 4 | 1 |
| ben | I'm bored. Entertain me. | 0.058 | 0.565 | 1 | 1 |
| ben | Do you trust people? | 0.006 | 0.808 | 3 | 1 |
| ben | What's the worst advice you've ever gotten? | 0.300 | 0.832 | 1 | 5 |
| ben | Describe yourself in one sentence. | 0.041 | 0.695 | 1 | 1 |
| erin | How's your day going? | 0.358 | 0.261 | 1 | 4 |
| erin | What do you think about modern life? | 0.009 | 0.613 | 1 | 3 |
| erin | Someone just cut me off in traffic. What should  | 0.809 | 0.443 | 1 | 1 |
| erin | Tell me something you care about. | 0.216 | 0.668 | 1 | 5 |
| erin | I'm bored. Entertain me. | 0.095 | 0.110 | 1 | 1 |
| erin | Do you trust people? | 0.030 | 0.456 | 1 | 1 |
| erin | What's the worst advice you've ever gotten? | 0.640 | 0.084 | 1 | 1 |
| erin | Describe yourself in one sentence. | 0.712 | 0.478 | 1 | 5 |
| jack | How's your day going? | 0.699 | 0.152 | 1 | 1 |
| jack | What do you think about modern life? | 0.105 | 0.731 | 1 | 4 |
| jack | Someone just cut me off in traffic. What should  | 0.013 | 0.206 | 1 | 3 |
| jack | Tell me something you care about. | 0.107 | 0.483 | 1 | 1 |
| jack | I'm bored. Entertain me. | 0.032 | 0.483 | 1 | 1 |
| jack | Do you trust people? | 0.345 | 0.703 | 1 | 4 |
| jack | What's the worst advice you've ever gotten? | 0.018 | 0.763 | 5 | 1 |
| jack | Describe yourself in one sentence. | 0.065 | 0.244 | 1 | 1 |
| bateman | How's your day going? | 0.208 | 0.472 | 5 | 1 |
| bateman | What do you think about modern life? | 0.209 | 0.357 | 5 | 1 |
| bateman | Someone just cut me off in traffic. What should  | 0.534 | 0.330 | 1 | 1 |
| bateman | Tell me something you care about. | 0.074 | 0.244 | 1 | 1 |
| bateman | I'm bored. Entertain me. | 0.297 | 0.774 | 1 | 1 |
| bateman | Do you trust people? | 0.072 | 0.174 | 5 | 5 |
| bateman | What's the worst advice you've ever gotten? | 0.102 | 0.283 | 1 | 1 |
| bateman | Describe yourself in one sentence. | 0.060 | 0.096 | 1 | 1 |
| alvy | How's your day going? | 0.014 | 0.532 | 1 | 5 |
| alvy | What do you think about modern life? | 0.007 | 0.206 | 3 | 5 |
| alvy | Someone just cut me off in traffic. What should  | 0.029 | 0.969 | 1 | 1 |
| alvy | Tell me something you care about. | 0.553 | 0.943 | 3 | 3 |
| alvy | I'm bored. Entertain me. | 0.273 | 0.057 | 1 | 1 |
| alvy | Do you trust people? | 0.578 | 0.891 | 5 | 1 |
| alvy | What's the worst advice you've ever gotten? | 0.024 | 0.971 | 1 | 1 |
| alvy | Describe yourself in one sentence. | 0.021 | 0.049 | 1 | 1 |
| ben | How's your day going? | 0.009 | 0.087 | 3 | 4 |
| ben | What do you think about modern life? | 0.168 | 0.426 | 5 | 3 |
| ben | Someone just cut me off in traffic. What should  | 0.655 | 0.358 | 1 | 3 |
| ben | Tell me something you care about. | 0.554 | 0.454 | 1 | 3 |
| ben | I'm bored. Entertain me. | 0.007 | 0.620 | 1 | 1 |
| ben | Do you trust people? | 0.024 | 0.069 | 5 | 4 |
| ben | What's the worst advice you've ever gotten? | 0.114 | 0.719 | 1 | 1 |
| ben | Describe yourself in one sentence. | 0.344 | 0.885 | 1 | 1 |
| erin | How's your day going? | 0.442 | 0.262 | 1 | 1 |
| erin | What do you think about modern life? | 0.034 | 0.056 | 1 | 3 |
| erin | Someone just cut me off in traffic. What should  | 0.046 | 0.053 | 1 | 1 |
| erin | Tell me something you care about. | 0.033 | 0.216 | 1 | 1 |
| erin | I'm bored. Entertain me. | 0.084 | 0.573 | 1 | 1 |
| erin | Do you trust people? | 0.032 | 0.046 | 1 | 1 |
| erin | What's the worst advice you've ever gotten? | 0.067 | 0.815 | 1 | 5 |
| erin | Describe yourself in one sentence. | 0.070 | 0.262 | 1 | 1 |
| jack | How's your day going? | 0.147 | 0.591 | 3 | 1 |
| jack | What do you think about modern life? | 0.131 | 0.269 | 1 | 5 |
| jack | Someone just cut me off in traffic. What should  | 0.242 | 0.709 | 1 | 5 |
| jack | Tell me something you care about. | 0.431 | 0.636 | 1 | 3 |
| jack | I'm bored. Entertain me. | 0.483 | 0.574 | 1 | 1 |
| jack | Do you trust people? | 0.441 | 0.643 | 5 | 4 |
| jack | What's the worst advice you've ever gotten? | 0.146 | 0.397 | 5 | 5 |
| jack | Describe yourself in one sentence. | 0.693 | 0.201 | 5 | 1 |
| bateman | How's your day going? | 0.677 | 0.248 | 1 | 1 |
| bateman | What do you think about modern life? | 0.137 | 0.288 | 1 | 5 |
| bateman | Someone just cut me off in traffic. What should  | 0.090 | 0.211 | 1 | 1 |
| bateman | Tell me something you care about. | 0.105 | 0.454 | 1 | 1 |
| bateman | I'm bored. Entertain me. | 0.057 | 0.632 | 1 | 1 |
| bateman | Do you trust people? | 0.047 | 0.079 | 1 | 5 |
| bateman | What's the worst advice you've ever gotten? | 0.122 | 0.403 | 5 | 1 |
| bateman | Describe yourself in one sentence. | 0.149 | 0.525 | 1 | 1 |
| alvy | How's your day going? | 0.664 | 0.778 | 4 | 5 |
| alvy | What do you think about modern life? | 0.052 | 0.804 | 5 | 5 |
| alvy | Someone just cut me off in traffic. What should  | 0.022 | 0.985 | 1 | 3 |
| alvy | Tell me something you care about. | 0.013 | 0.204 | 3 | 1 |
| alvy | I'm bored. Entertain me. | 0.816 | 0.548 | 5 | 1 |
| alvy | Do you trust people? | 0.013 | 0.891 | 3 | 1 |
| alvy | What's the worst advice you've ever gotten? | 0.007 | 0.140 | 1 | 1 |
| alvy | Describe yourself in one sentence. | 0.090 | 0.209 | 1 | 1 |
| ben | How's your day going? | 0.014 | 0.094 | 3 | 3 |
| ben | What do you think about modern life? | 0.130 | 0.277 | 4 | 1 |
| ben | Someone just cut me off in traffic. What should  | 0.574 | 0.588 | 1 | 1 |
| ben | Tell me something you care about. | 0.018 | 0.593 | 3 | 1 |
| ben | I'm bored. Entertain me. | 0.347 | 0.085 | 1 | 1 |
| ben | Do you trust people? | 0.033 | 0.513 | 1 | 3 |
| ben | What's the worst advice you've ever gotten? | 0.237 | 0.656 | 3 | 1 |
| ben | Describe yourself in one sentence. | 0.651 | 0.073 | 1 | 1 |
| erin | How's your day going? | 0.216 | 0.555 | 4 | 5 |
| erin | What do you think about modern life? | 0.007 | 0.223 | 1 | 1 |
| erin | Someone just cut me off in traffic. What should  | 0.050 | 0.178 | 1 | 5 |
| erin | Tell me something you care about. | 0.105 | 0.249 | 1 | 1 |
| erin | I'm bored. Entertain me. | 0.518 | 0.498 | 1 | 1 |
| erin | Do you trust people? | 0.043 | 0.170 | 1 | 1 |
| erin | What's the worst advice you've ever gotten? | 0.185 | 0.716 | 1 | 5 |
| erin | Describe yourself in one sentence. | 0.083 | 0.432 | 1 | 5 |
