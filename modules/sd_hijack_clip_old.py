import logging

def process_text_old(self, texts):
    id_start = self.id_start
    id_end = self.id_end
    maxlen = self.max_length  # you get to stay at 77
    used_custom_terms = []
    remade_batch_tokens = []
    hijack_comments = []
    hijack_fixes = []
    token_count = 0

    cache = {}
    batch_tokens = self.tokenize(texts)
    batch_multipliers = []
    batch_multipliers_solo_emb = []
    for tokens in batch_tokens:
        tuple_tokens = tuple(tokens)

        if tuple_tokens in cache:
            remade_tokens, fixes, multipliers, multipliers_solo_emb = cache[tuple_tokens]
        else:
            fixes = []
            remade_tokens = []
            multipliers = []
            multipliers_solo_emb = []
            mult = 1.0

            i = 0
            while i < len(tokens):
                token = tokens[i]

                embedding, embedding_length_in_tokens = self.embeddings.find_embedding_at_position(tokens, i)
                if isinstance(embedding, dict):
                    if 'open' in self.__class__.__name__.lower():
                        embedding = embedding.get('g', embedding)
                    else:
                        embedding.pop('g', None)
                        embedding = next(iter(embedding.values()))

                mult_change = self.token_mults.get(token) if self.opts.enable_emphasis else None
                if mult_change is not None:
                    mult *= mult_change
                    i += 1
                elif embedding is None:
                    remade_tokens.append(token)
                    multipliers.append(mult)
                    multipliers_solo_emb.append(mult)
                    i += 1
                else:
                    emb_len = int(embedding.vec.shape[0])
                    fixes.append((len(remade_tokens), embedding))
                    remade_tokens += [0] * emb_len
                    multipliers += [mult] * emb_len
                    multipliers_solo_emb += [mult] + ([1.0] * (emb_len-1))
                    used_custom_terms.append((embedding.name, embedding.checksum()))
                    i += embedding_length_in_tokens

            if len(remade_tokens) > maxlen - 2:
                vocab = {v: k for k, v in self.tokenizer.get_vocab().items()}
                ovf = remade_tokens[maxlen - 2:]
                overflowing_words = [vocab.get(int(x), "") for x in ovf]
                overflowing_text = self.tokenizer.convert_tokens_to_string(''.join(overflowing_words))
                logging.warning(f"\033[33mWarning:\033[0m too many input tokens; some ({len(overflowing_words)}) have been truncated:\n{overflowing_text}\n")

            token_count = len(remade_tokens)
            remade_tokens = remade_tokens + [id_end] * (maxlen - 2 - len(remade_tokens))
            remade_tokens = [id_start] + remade_tokens[0:maxlen - 2] + [id_end]
            cache[tuple_tokens] = (remade_tokens, fixes, multipliers, multipliers_solo_emb)

        multipliers = multipliers + [1.0] * (maxlen - 2 - len(multipliers))
        multipliers = [1.0] + multipliers[0:maxlen - 2] + [1.0]

        multipliers_solo_emb = multipliers_solo_emb + [1.0] * (maxlen - 2 - len(multipliers_solo_emb))
        multipliers_solo_emb = [1.0] + multipliers_solo_emb[0:maxlen - 2] + [1.0]

        remade_batch_tokens.append(remade_tokens)
        hijack_fixes.append(fixes)
        batch_multipliers.append(multipliers)
        batch_multipliers_solo_emb.append(multipliers_solo_emb)
    return batch_multipliers, batch_multipliers_solo_emb, remade_batch_tokens, used_custom_terms, hijack_comments, hijack_fixes, token_count


def forward_old(self, texts):
    batch_multipliers, batch_multipliers_solo_emb, remade_batch_tokens, used_custom_terms, hijack_comments, hijack_fixes, _token_count = process_text_old(self, texts)

    chunk_count = max([len(x) for x in remade_batch_tokens])

    if self.opts.return_batch_chunks:
        return (remade_batch_tokens, chunk_count)

    self.hijack.comments += hijack_comments

    if len(used_custom_terms) > 0:
        embedding_names = ", ".join(f"{word} [{checksum}]" for word, checksum in used_custom_terms)
        self.hijack.comments.append(f"Used embeddings: {embedding_names}")

    self.hijack.fixes = hijack_fixes
    return self.process_tokens(remade_batch_tokens, batch_multipliers, batch_multipliers_solo_emb)

def process_texts_past(self, texts):
    batch_multipliers, batch_multipliers_solo_emb, remade_batch_tokens, used_custom_terms, hijack_comments, hijack_fixes, _token_count = process_text_old(self, texts)
    return [(remade_batch_tokens, batch_multipliers)]