# Third-Party Notices

lwpm is licensed under the MIT License (see `LICENSE`). It bundles one piece of
third-party data whose original copyright notices are reproduced below, as
required by their (permissive) license terms.

## Bundled wordlist — `src/lwpm/data/wordlist.txt`

The bundled diceware wordlist is derived from the **SCOWL (Spell Checker
Oriented Word Lists)** collection, by way of the Debian `wbritish-small`
package (`/usr/share/dict/british-english-small`). It was produced by filtering
that dictionary to plain lowercase a–z words of 4–9 characters (removing
apostrophes, proper nouns, and punctuation) and de-duplicating the result.

SCOWL and its constituent sources are distributed under permissive and
public-domain terms. The two notices below are reproduced to satisfy SCOWL's
and Ispell's "retain the copyright notice" conditions; the remaining components
(Moby, 12Dicts, ENABLE, the UK English Wordlist, WordNet, the U.S. Census name
lists, and the Jargon File) are public domain or carry equivalently permissive
terms.

### SCOWL

> SCOWL (Spell Checker Oriented Word Lists) is a collection of English word
> lists maintained by Kevin Atkinson.
>
> The collective work is Copyright 2000-2011 by Kevin Atkinson.
>
> Permission to use, copy, modify, distribute and sell these word lists, the
> associated scripts, the output created from the scripts, and its
> documentation for any purpose is hereby granted without fee, provided that the
> above copyright notice appears in all copies and that both that copyright
> notice and this permission notice appear in supporting documentation. Kevin
> Atkinson makes no representations about the suitability of this array for any
> purpose. It is provided "as is" without express or implied warranty.

### Ispell (British spellings, via the VARCON package)

> Copyright 1993, Geoff Kuenning, Granada Hills, CA
> All rights reserved.
>
> Redistribution and use in source and binary forms, with or without
> modification, are permitted provided that the following conditions are met:
>
> 1. Redistributions of source code must retain the above copyright notice,
>    this list of conditions and the following disclaimer.
> 2. Redistributions in binary form must reproduce the above copyright notice,
>    this list of conditions and the following disclaimer in the documentation
>    and/or other materials provided with the distribution.
> 3. All modifications to the source code must be clearly marked as such.
>    Binary redistributions based on modified source code must be clearly marked
>    as modified versions in the documentation and/or other materials provided
>    with the distribution.
> 5. The name of Geoff Kuenning may not be used to endorse or promote products
>    derived from this software without specific prior written permission.
>
> THIS SOFTWARE IS PROVIDED BY GEOFF KUENNING AND CONTRIBUTORS ``AS IS'' AND ANY
> EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
> WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
> DISCLAIMED. IN NO EVENT SHALL GEOFF KUENNING OR CONTRIBUTORS BE LIABLE FOR ANY
> DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
> (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
> LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
> ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
> (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
> SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The full SCOWL copyright file, listing every constituent source and its terms,
ships with the Debian `wbritish-small` package at
`/usr/share/doc/wbritish-small/copyright`.
