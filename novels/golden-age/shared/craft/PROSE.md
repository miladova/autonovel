# PROSE REFERENCE

How sentences, paragraphs, scenes and dialogue hold together. This is
the register-neutral companion to CRAFT.md: nothing here says whether a
book should sound like Hilary Mantel or Robert Harris. It says what
every published craft authority agrees a reader needs in order to feel
a page move, and it names the source for each claim so that a rule can
be checked against the book it came from rather than argued about.

**Precedence.** `books/<book>/voice.md` decides register (reader,
models, cadence, what the narrator refuses) and may set numeric
calibration for its own book. It is not expected to override anything
here, because nothing here is register. Where it does, the voice file
wins, as with CRAFT.md.

**What is sourced and what is not.** Each section ends with rules the
sources support and, where the pipeline adds a threshold the sources
do not give, says so in square brackets: `[pipeline heuristic]`. §9
lists the common "rules" that turned out to be folklore when checked.
Treat those as candidates to look at, never as failures.

---

## 1. Sentences connect: the known-new contract

**Sources.** Joseph M. Williams, *Style: Lessons in Clarity and Grace*
(cohesion chapters); George Gopen and Judith Swan, "The Science of
Scientific Writing" (*American Scientist*, 1990); Steven Pinker, *The
Sense of Style*, ch. 5 "Arcs of Coherence".

Williams: "Within a sentence, move from old to new, from familiar to
unfamiliar, from less important to more important. The beginning of a
sentence serves to prepare the new idea you are going to put forward in
its end. The beginning looks back, the end looks forward." A passage
whose topics "shift randomly" leaves the reader "dislocated,
disoriented, out of focus." Gopen and Swan: readers "naturally
emphasize the material that arrives at the end of a sentence" and
expect the opening of a sentence to be "a story about whoever shows up
first"; when the writer violates this, "readers are left to construct
the logical linkage by themselves." Pinker: "Topic, then comment.
Given, then new." Connectives such as *because, so, but, which meant,
until, instead* are "the unsung heroes of lucid prose"; readers hunt
for coherence between sentences "even when there is none."

This is the mechanism behind the complaint "it reads like a list of
statements." Each sentence may be true and clear, and still the reader
does the joining, because each one opens on something new and closes
on something nothing picks up.

**Rules the sources support.**

1. A sentence opens on something already in play (the last sentence's
   result, object, person or question) and puts the new element at the
   end. The next sentence opens on that new element. Williams's
   "domino" pattern.
2. Within a paragraph the grammatical subjects form a short consistent
   set, the paragraph's "characters". Subject-hopping is the visible
   sign of incoherence.
3. A new thread enters in the stress position of a paragraph's opening
   sentence, not buried mid-paragraph.
4. Connectives are a virtue; underuse is the common fault. No source
   gives a density. [pipeline heuristic: in a passage meant to flow, a
   third of narrative sentences carrying a join is a healthy sign; a
   long run with none is the thing to look at.]
5. Do not vary a name for elegance. Williams: "Do not use two different
   words for one concept when your readers might take them for two
   different concepts." The Turkey City Lexicon's "Burly Detective
   Syndrome" is the fiction version.

**Checks.** Read each paragraph and name the word or idea in its first
sentence that comes from the paragraph before; if nothing does, the
paragraph is unjoined. Count paragraphs that open on a bare
subject-and-verb statement introducing a new subject; a run of them is
the list-of-statements signature.

---

## 2. Paragraphs: break on turns, vary the length

**Sources.** Ursula K. Le Guin, *Steering the Craft* ("Crowding and
Leaping"); Francine Prose, *Reading Like a Writer*, ch. 4; Louise
Harnby (crime and thriller editor) on one-line paragraphs; *Writing
Excuses* 12.14, "Controlling Pacing with Structure".

Le Guin: "The chief duty of a narrative sentence is to lead to the next
sentence." On selection: "What you leap over is what you leave out. And
what you leave out is infinitely more than what you leave in." "Listing
is not describing. Only the relevant belongs." Prose holds that there
are "no general rules" for a well-made paragraph, only examples; the
break is a breath and a turn. Harnby: "The staccato rhythm of one-line
paragraphs is interruptive, both rhythmically and visually," useful at
a suspenseful finale, not as a default. *Writing Excuses*: a
one-sentence paragraph "can really drive a point home," and Dan Wells
has to "force myself to not overuse them"; Mary Robinette Kowal:
paragraphing should reflect "the character's experience."

**Rules the sources support.**

1. Break on a turn: a new speaker, a new stimulus, a shift of
   attention. Not on a word count. No source gives a length.
2. Vary length. A run of equal-length paragraphs is the detectable
   fault. [pipeline heuristic: four or more consecutive paragraphs
   within twenty per cent of the same length is worth a look.]
3. One-line paragraphs are a reserved effect for the beat the reader
   should stop on, and for scene or chapter ends. [pipeline heuristic:
   more than about two per thousand words is a candidate for overuse.]
4. Never split a paragraph to improve a count. A paragraph is a unit of
   attention, and halving one makes two unjoined ones.
5. A paragraph of sensory items with no selecting consciousness fails
   "only the relevant belongs."

---

## 3. Rhythm: variance, not an average

**Sources.** Gary Provost, *100 Ways to Improve Your Writing* (1985),
the "This sentence has five words" passage; Le Guin, *Steering the
Craft*; Ken Follett on "transparent prose" (writerswrite.co.za
collection of his Masterclass remarks).

Provost's passage makes one point: monotony comes from uniform length,
in either direction, and a long sentence "earns" its length by
following short ones. Le Guin on the short-is-best dogma: "A convicted
criminal might agree. I don't." On all-short prose: "the thump-thump
beat gives it a false simplicity that soon just sounds stupid… See
Spot. See Jane. See Spot bite Jane." "The test of a sentence is, Does
it sound right?" Follett: "I've failed dreadfully if you have to read a
sentence twice."

No authoritative dataset gives an average sentence length by genre; the
figures that circulate (thrillers 10 to 15 words, literary 18 to 25)
are marketing content with no data behind them. A book's voice file may
set its own band as calibration; this document does not.

**Rules the sources support.**

1. Measure variance within a paragraph, not the mean. Uniform cadence is
   the fault, whether uniformly short or uniformly long.
2. After three or more short sentences expect a longer one; after a
   long sentence a short one lands harder.
3. A long sentence is fine if it parses in one pass (Follett). A
   sentence that must be read twice fails, whatever its length.
4. No absolute ceiling on words per sentence is supported. A book may
   impose one as calibration; the judge then applies the book's number.

---

## 4. Psychic distance and free indirect style

**Sources.** John Gardner, *The Art of Fiction* (1983), p. 111; Emma
Darwin, "Psychic Distance: What It Is and How to Use It" and "Six
Thoughts about Psychic Distance" (*This Itch of Writing*); James Wood,
*How Fiction Works*.

Gardner's ladder, from far to close: (1) "It was winter of the year
1853. A large man stepped out of a doorway." (2) "Henry J. Warburton
had never much cared for snowstorms." (3) "Henry hated snowstorms." (4)
"God how he hated these damn snowstorms." (5) "Snow. Under your collar,
down inside your shoes, freezing and plugging up your miserable soul…"
His concern is "sudden shifts in psychic distance, not gradual change,"
because a lurch snaps the reader out of the "vivid and continuous
dream." Darwin: "Gardner's point is not that one distance is better
than another"; good fiction has a "rhythm of intimacy and distance";
far-out "for a long stretch of time can get very dull," close-in for
too long is "claustrophobic." The farther-out levels are "more tell-y
and inform-y: summarising and explaining," and that is their job;
levels 2 to 4 are where "most of modern fiction spends most of its
time" because they carry information while keeping the story moving.
Wood on free indirect style: the narrator "hovers around the
consciousness" of the character and lets "the character dictate the
exact right wrong word"; in Joyce's "Lily, the caretaker's daughter,
was literally run off her feet," *literally* is Lily's word, not the
author's.

This is how a close-third narrator explains the world without
lecturing: the explanation sits at level 2 or 3, coloured by the
character's diction and judgment, and the sentence stays theirs.

**Rules the sources support.**

1. Move at most one rung between adjacent sentences. A level-1 sentence
   straight after a level-4 or level-5 sentence is a lurch.
2. World-explaining belongs at levels 2 to 3 and is coloured by the
   viewpoint character: their words, their comparison, their judgment
   of why it matters now. An information sentence with no
   character-coloured word, dropped into a level-4 passage, is the
   lecture signature.
3. The free-indirect test: could the sentence's evaluative words be the
   character's? If only the author could say them, the narration has
   slipped out of the character without signalling.
4. Vary distance within a scene. Sustained level 1 is dull, sustained
   level 5 exhausting.
5. Interior thought is written as thought, not reported: Browne and
   King turn "He wondered why…" into "Why did he…?" (see §6).

---

## 5. Scenes are chains of cause and effect

**Sources.** Dwight Swain, *Techniques of the Selling Writer* (1965);
Jack Bickham, *Scene and Structure* (1993), esp. ch. 3 "Structure in
Microcosm: Cause and Effect"; Randy Ingermanson, "Writing the Perfect
Scene"; Robert McKee, *Story* and "Do Your Scenes Turn?"
(mckeestory.com); Ken Follett (Entrepreneur interview, 2020); Lee
Child, "A Simple Way to Create Suspense" (*New York Times*, 2012);
James Scott Bell, *Plot & Structure*; Kurt Vonnegut, *Bagombo Snuff
Box*, rule 3; Sandra Scofield, *The Scene Book*.

**Scene and sequel (Swain).** A scene is "a unit of conflict": goal,
conflict, disaster. A sequel is "a unit of transition that links two
scenes": reaction, dilemma, decision, and the decision becomes the next
scene's goal. A scene "should not end in complete victory unless the
story is ending."

**Motivation and reaction (Swain, Bickham, Ingermanson).** Beneath the
scene sits the smallest unit: an external, observable stimulus, then
the viewpoint character's response. Bickham: "Stimulus must be
external—that is, action or dialogue." "For every stimulus, you must
show a response. For every desired response, you must provide a
stimulus." "Response usually must follow stimulus at once." Where the
response is not obviously logical, the character's thought goes between
the two; without it "the action starts to feel flat and unimportant."
Ingermanson: inside a reaction the order is feeling, then reflex, then
deliberate action or speech, "based on what is physiologically
possible"; put a paragraph break between motivation and reaction.

**Does the scene turn (McKee).** "A SCENE is an action through conflict
in more or less continuous time and space that turns the value-charged
condition of a character's life on at least one value with a degree of
perceptible significance." The test: write down the charge of the value
at stake at the scene's opening and at its close; "If the answer you
write down at the end of the scene is the same note you made at the
opening," the scene is a nonevent. A scene that exists only to deliver
exposition: "a disciplined writer will trash it and weave its
information into the film elsewhere." His commandment: "Thou shalt not
give exposition for strictly exposition's sake. Dramatize it. Convert
exposition to ammunition."

**The want (Vonnegut, Bickham, Scofield).** "Every character should want
something, even if it is only a glass of water." Bickham: the goal is
stated early enough that the reader forms a yes/no "scene question";
the ending is a "tactical disaster," a plain No, or "Yes, but…" with a
new complication. Scofield's "pulse" is the state of desire or need
that makes the scene matter; it can be subtle, but it is there.

**Propulsion (Child, Follett, Bell).** Child: "The basic narrative fuel
is always the slow unveiling of the final answer," and it works "page
to page, paragraph to paragraph, line to line": ask a question, delay
the answer. Follett: "the story needs to turn every four-to-six pages";
a turn can be "as small as someone telling a lie" or "murder," so long
as "the situation changes for the characters and the problems that
they're facing." "If nobody gets into trouble, there's no story." Bell:
scenes are HIP, "start with a Hook, amp the Intensity during, and end
with a Prompt," and the read-on prompt matters most when the scene ends
a chapter.

This is the structural reason paragraphs chain: in a scene built this
way every paragraph is either something that happens to the viewpoint
character or what they feel, think and do about it, so each one is
caused by the last. A paragraph that is neither, pure information or
authorial summary, is the one that reads as a disconnected statement.

**Rules the sources support.**

1. Every scene has one viewpoint goal the reader can name as a yes/no
   question by the end of its opening third. The want is dramatised
   (action, oblique dialogue, free-indirect thought), not announced in
   summary. The announcement has a recognisable shape, "What X wanted
   from the afternoon was…", "X needed one thing from the hour…", and
   a reader who meets it twice sees the outline under the prose. Used
   at all, once a chapter, never as the opening device of consecutive
   scenes.
2. The goal is pursued against external, visible opposition in
   continuous time, not recalled.
3. Every paragraph inside a scene is classifiable as motivation
   (external, observable) or reaction (feeling, thought, then act or
   speech). A reaction follows its stimulus at once; a stimulus gets a
   reaction before the next stimulus.
4. The scene ends with the question answered against the character: No,
   or Yes-but. Never a clean Yes except the last scene of the book.
5. A value named at the open carries a different charge at the close,
   or the scene is cut or merged. Apply McKee's test literally: write
   the two charges down.
6. Something changes the situation at least every four to six printed
   pages, roughly every 1,200 to 1,800 words (Follett).
7. A chapter opens with or implies an unanswered question and ends
   before answering it, on the disaster or on a Bell prompt (impending
   disaster, portent, mysterious line, secret revealed, decision,
   reversal), not on narrator reflection.
8. A clock set on the page (a deadline, an ultimatum, a promise with a
   date) is paid on the page: the scene in which it runs out, is met
   or is bought off is dramatised, with the viewpoint character doing
   the thing that changes it. Swain's sequel ends in a decision that
   becomes the next scene's goal; a chapter that ends on a clock and a
   next chapter that opens after the reprieve ("she wrote; I have till
   autumn") has skipped the scene the clock was set for, and readers
   name it as the missing scene.
9. The scene a chapter exists for, the turn its outline beat names, is
   played in the present of the scene (continuous time, direct speech
   for the decisive lines, the other party's reaction), never recalled
   in pluperfect from after the event and never followed by a label
   for the feeling it produced. Summary is for logistics (Follett's
   "undramatic summary" is what the modern form cut); the turn is a
   scene.

---

## 6. Dialogue

**Sources.** Renni Browne and Dave King, *Self-Editing for Fiction
Writers*; Sol Stein, *Stein on Writing* and *How to Grow a Novel*;
Elmore Leonard, "Ten Rules of Writing" (*New York Times*, 2001); the
Turkey City Lexicon (Shiner and Sterling, SFWA); Elizabeth George,
*Write Away*; Mark Liberman, "Dialogue proportion," *Language Log*
(2017).

Browne and King: "Prefer 'said.'" "Kill -ly adverbs." "Use beats
(little actions)," but beats that describe the dialogue, or so many
that "the dialogue is choppy," are faults. "Watch for the dialogue or
interior monologue that is only there to feed information to the
reader – cut it!" "Resist the urge to explain." Stein: "Dialogue is not
a recording of speech, it is an invented language." "Whenever possible,
dialogue should be adversarial. Think of dialogue as confrontations or
interrogations." "The best dialogue contains responses that are
indirect, oblique." His four questions for any exchange: what is its
purpose; does it begin or heighten a conflict; does it create tension
or curiosity; does it build to a turn or a change in the relationship
of the speakers. "In life, adversarial exchanges vent the speakers'
emotions; in dialogue, such exchanges are designed to move a story
forward." Leonard: "Never use a verb other than 'said' to carry
dialogue." "Never use an adverb to modify the verb 'said'." "Try to
leave out the part that readers tend to skip," and readers do not skip
dialogue. The Lexicon's "As You Know, Bob": "A pernicious form of
info-dump through dialogue, in which characters tell each other things
they already know, for the sake of getting the reader up-to-speed."
George's "Talking Heads Avoidance Device": an ongoing physical activity
that anchors a conversation. Follett: modern storytelling cuts "from
one dramatic scene to the next," whereas Victorian novelists "felt free
to write long passages of undramatic summary."

On proportion, Liberman measured the share of text inside quotation
marks: Christie 49 to 79 per cent, Elmore Leonard 34 to 61, Dan Brown's
*Da Vinci Code* 30, Hemingway's *Old Man and the Sea* 15, Woolf's *To
the Lighthouse* 3. There is no authoritative target; the oft-quoted
"70 per cent for thrillers" came from a panel, not data.

**Rules the sources support.**

1. Tag with *said* or an action beat. Any other speech verb and any
   adverb on *said* is a candidate cut.
2. Beats mark turns; a beat on every line makes the dialogue choppy.
3. Every exchange passes at least one of Stein's four questions. A pure
   question-answer-question-answer run of three or more turns, in which
   one speaker exists to prompt facts from the other, fails all four:
   it is a catechism, not a conversation. Replies should sometimes be
   oblique.
4. Information in dialogue is allowed only when the listener does not
   already know it and the speaker has a motive to say it now. Even
   then, a character with a lot to explain gets one speech and a
   reaction, not the same material cut into eight answers to prompted
   questions.
5. Dramatise an exchange that turns a value or a relationship;
   summarise, inside narration, an exchange that only transfers
   information ("he asked who the man was, and she told him"). The
   choice is made by Stein's questions, not by a word budget. The
   reverse failure follows from over-applying this rule: a bargain, an
   accusation or a refusal rendered as indirect speech ("X said that
   he…, and Y said that…") keeps the reader one step from the people
   at the moment they most want to hear them (Browne and King, "Show
   and Tell": the big moments are scenes). When one speaker is trying
   to move the other, the decisive lines are in quotation marks.
6. Every dialogue scene has a physical anchor and external stakes.
7. Interior thought is direct ("Why did he…?") rather than reported ("He
   wondered why…").
8. No percentage of dialogue is a rule. A book may set a floor or
   ceiling as calibration; the judge applies the book's number and
   does not invent one.

---

## 7. Information: who needs it now

**Sources.** Emma Darwin, "Ten Things That Go Wrong With Historical
Fiction" and her Historia column on information "without it being
clunkingly obvious"; Robert Harris (Walter Scott Prize interview;
Goodreads Q&A); Chuck Palahniuk, "Nuts and Bolts: 'Thought' Verbs"
(LitReactor, 2013); the Turkey City Lexicon; Hemingway, *Death in the
Afternoon* (1932); Renni Browne and Dave King, *Self-Editing for Fiction
Writers*, "Once Is Usually Enough".

Darwin: "Good technique is the key to good writing, whereas good
research is merely necessary, not sufficient." Information is filtered
"through narrative setup, POV and voice"; "All the other informational
darlings should be tipped into the bin." Do not point forwards: "Don't
make them unnaturally perceptive or farsighted, let alone clairvoyant:
the reader will feel explained-at." Do not spell out parallels to now:
"You need the reader to reach the 4, the connection, on their own."
Harris: "I generally know about ten times more than I'll ever use"; the
method is to tell the story "using only those facts that are
relevant," and "never directly to contradict the historical record…
What I do feel is legitimate is to condense and simplify: to dig out
the bones of a narrative. And of course I invent scenes to fit in and
around the known facts." The Lexicon: an infodump is where "all action
stops as the author assumes center stage and lectures"; information
"worked unobtrusively into the story's basic structure" is the thing to
aim for, and a brief deft dump is acceptable. Hemingway's iceberg: a
writer who "knows enough of what he is writing about… may omit things
that he knows." Its limit, noted by his critics: omit what you do not
know and you make "a hole in the story." The iceberg governs research,
not clarity. Palahniuk: the thought verbs ("Thinks, Knows, Understands,
Realizes, Believes, Wants, Remembers…") are to be unpacked into what
the character observes and does, "Adam knew Gwen liked him" becoming
Gwen leaning on his locker between classes; a paragraph that opens with
a thought-verb thesis "steals the thunder of what follows." He frames
the ban as a training exercise, "at least for the next half year," not
a law. The Lexicon on show-don't-tell: "Rigid adherence… can become
absurd. Minor matters are sometimes best gotten out of the way in a
swift, straightforward fashion."

**Rules the sources support.**

1. Every passage of information is attributable to a character's need
   in that moment: someone in the scene has a reason to notice or say
   it now, and it changes what they do (McKee's "ammunition").
2. The sentence that carries it is coloured by that character (§4), and
   enters at psychic distance 2 to 3. A fact the reader needs but no
   character would voice goes in as acknowledged narration at level 1
   to 2, kept short.
3. **The story is lived forward.** No character foresees the future or
   voices a modern parallel (Darwin's "clairvoyant" fault), and the
   narrator does not forecast either. Irving Stone: the novelist "may not
   turn himself into an a posteriori prophet"; stage the story "as though
   it were happening right now." Mantel: the writer knows the outcome,
   "so does the reader - but the characters don't", and "the suspense
   grows in the gap." A narrator's flash-forward ("in 1519 he would…",
   "thirty years later…", "it was the first of many…") moves the reader
   from inside the scene to the end of the life looking back, and spends
   the suspense the scene has just built. A book with one in most
   chapters reads as remembered episodes of a life already known, which
   is an anecdote chain however well the chapters are made.
   Foreshadowing is done inside the story's own time: a planted object, a
   fear, a question a character asks and nobody answers, a danger the
   reader can see and the character can't (Hitchcock's bomb;
   `EDITING.md` V2, V3, H7). The one exception: a narration that
   declares a retrospective narrator in its voice file may forecast
   where the forecast sharpens the book's central question into *how*
   or *why* (Muriel Spark tells us early in *The Prime of Miss Jean
   Brodie* who will betray Brodie, and the book becomes the why). Then: a
   handful in the whole book, never at a scene's climax, never a moral,
   never "little did he know". Candidates for the judge, not failures:
   "would one day," "years later," "would become," a year past the
   chapter's story time (`autonovel mechanical prolepsis` lists them).
   *Decision of 2026-10-18,* replacing the 2026-10-15 rule that allowed
   one "promise line" a chapter: on the first book it was applied to,
   flash-forwards in 19 of 24 chapters were the main reason an editor's
   full read found it a string of anecdotes. A planted detail paid later
   is still a callback, not a cause (CRAFT.md §1 "Causation, not
   sequence").
4. A proper noun the reader cannot place (a town, a fortress, a coin,
   an institution, a battle) is glossed in the sentence it first
   appears in, by the character who needs it: what it is and why it
   matters now. Chalking "SCUTARI" on a slate is a scene; the reader
   still needs, in that sentence or the next, that it is the
   Republic's fortress in Albania and the Turk is outside it. This is
   §7.1 applied to names: the need is the reader's, voiced by someone
   on the page.
5. Thought verbs and emotion labels are candidates, not failures: the
   fix is to unpack into observable action, not to delete the
   information. A plain register may name a state once and then show
   it; a literary register may show without naming. Both are craft.
6. Telling is correct for minor matters and transitions. Do not ban it.
7. Prefer evidence first, conclusion last or implied, over a thesis
   sentence followed by its proof.
8. Research depth (Harris's ten times more, Mantel's "stick by the
   truth" because it is "better, stranger, stronger") is a
   foundation-stage rule; at the sentence level the only question is
   who needs this now.
9. **Say it once.** Browne and King's editing checklist ("Once Is
   Usually Enough"): find the places where the writing does the same
   thing twice, keep the stronger and cut the weaker phrase, sentence or
   scene; their chapter holds that repeating an effect weakens a page as
   surely as repeating a word. A fact, a rule, an explanation, who a
   person is, or what happened in an earlier scene is given once in the
   book, where it first matters. Afterwards it gets at most a clause,
   and only when the reader has been away from it for several chapters
   (CHARACTER.md's re-anchor rule). The common forms: the narrator makes
   a point and a character makes it again, or the reverse (a character
   telling another what both know is §6.4); an explanation given again a
   few pages on because a reader got lost the first time (fix the first
   one); a paragraph near a chapter's start restating the book's
   situation, the "story so far"; the same description attached to a
   person every time they come back; an earlier scene retold where a
   clause would point back to it; a sum, a vote count or a rule recited
   in full each time it matters. A revision that clarifies something
   replaces the first statement or folds into it; it never adds a second
   statement beside the first. In historical fiction this cuts no
   period: the gloss stays, once. [pipeline heuristic: a point made
   three times in one chapter, or a story-so-far opening, holds the
   chapter under the dimension floor; `autonovel mechanical repeats`
   lists repeated wording as candidates, and the judge reads for the
   same point in new words, which no scanner sees.] *Decision of
   2026-10-25:* on one book an author two-thirds into chapter 1 found it
   "long and a bit slow" with "repetition"; the chapter explained four
   times who chooses the Emperor and stated one rule five times, nearly
   every chapter did the same, and every check had passed it because
   each looked for a term explained twice, never an idea.

---

## 8. Endings: stop on the turn

**Sources.** Bickham (the disaster); McKee (the charge test); Bell (the
read-on prompt); Emma Darwin, "Handclasps, Explosions, and Ribbons and
Bows"; Dear Editor on varying chapter-end devices; Jacqui Banaszynski
(Nieman Storyboard) on the tidy closing line.

Bickham: a scene ends on a "tactical disaster" that "closes off easy
routes forward"; "tighten the noose around the lead character's neck."
Darwin on endings: "less is almost always more. Maybe you just need to
stop where you are"; aftermath summary is "a set of ticked boxes";
avoid "ribbons and bows." Banaszynski on the closing quotation that
ties "a tidy bow on the very untidy real-world stories." Bell: end "a
paragraph or two early," but take care the reader does not feel
manipulated. Dear Editor: the same device every chapter becomes
"melodramatic, or simply… too much of the same"; alternate with a
misgiving, or a happy moment that hints at trouble.

**Rules the sources support.**

1. At least one named value flips charge per scene and the flip is not
   reversed within the chapter. This is the craft form of CRAFT.md's
   stability-trap rule.
2. The last paragraph of a chapter contains the disaster or a read-on
   prompt, not narrator reflection or summary.
3. Vary the closing device across consecutive chapters.
4. [pipeline heuristic] A final sentence that is an abstract
   generalisation with no concrete noun in it is worth a look. No
   editor names "the epigram closer" as a vice; the sourced principle
   is "don't summarise or moralise after the turn."

---

## 9. Folklore: things this document does not claim

Checked and found unsupported or unsourced. A voice file may adopt any
of them as calibration for its own book; none is a general rule.

- Average sentence length by genre (thrillers 10 to 15 words, literary
  18 to 25). Marketing content, no data.
- An absolute words-per-sentence ceiling.
- A dialogue percentage (the "70 per cent for thrillers" figure came
  from a panel; measured thrillers run from 30 to 60).
- Chapter length norms (1,500 to 3,000 words for thrillers). Secondary
  sites only.
- "The epigram closer" as a named editorial vice.
- Follett's line "the reader must always know what the characters
  want." Not found in any Follett source; Vonnegut and Bickham carry
  the same rule with sources.
- Any fixed paragraph length.
- Hemingway's "seven-eighths" figure (secondary); the 1932 "one-eighth
  above water" is the primary.
- Motivation-reaction units and stimulus-response are commercial-fiction
  doctrine (Swain, Bickham, Ingermanson). Literary sources do not
  endorse them and Blake Butler attacks the continuous-dream premise.
  Apply them to scenes meant to be immersive; a book in a different
  mode may say so in its voice file.

---

## 10. The judge's checklist

One line per checkable item, with the section it comes from. Report
counts, quote the worst instance, and treat the bracketed thresholds as
pipeline heuristics the book's voice file may override.

- §1 Unjoined paragraphs: first sentence picks up nothing from the one
  before. Count them. [flag at more than three in a chapter]
- §1 Bare openers: narrative paragraphs opening on a new
  subject-and-verb statement. [flag at more than one in five]
- §1 Connectives: share of narrative sentences carrying a join. [below
  a quarter in a passage meant to flow is worth a look]
- §2 Paragraph length variance; one-line paragraphs per thousand words
  [about two]; any paragraph split with no turn at the break.
- §3 Sentence-length variance within paragraphs; any sentence that
  needs a second read.
- §4 Psychic-distance lurches of more than one rung between adjacent
  sentences; information sentences with no character-coloured word
  inside a close passage.
- §5 Scene want nameable as a yes/no question from the opening third;
  every paragraph classifiable as motivation or reaction; the scene
  ends No or Yes-but; McKee's two charges differ; a turn at least every
  1,200 to 1,800 words.
- §5.1 Announced wants ("What X wanted was…") as scene openers: count
  them across the chapter and the previous one. [flag at two in a
  chapter, or the same shape opening consecutive scenes]
- §5.8 Clocks: every deadline, ultimatum or dated promise the previous
  chapter left open, and whether this chapter pays it on the page,
  carries it by name, or drops it. [flag any clock resolved only in
  summary]
- §5.9 The chapter's biggest turn: played in continuous time with
  direct speech, or recalled in pluperfect and labelled? Quote it.
- §6.5 Confrontations in indirect speech ("X said that…, and Y said
  that…"): count and quote the worst. [flag at more than two in a
  chapter]
- §6 Speech verbs other than *said*, adverbs on *said*; a beat on every
  line; question-answer runs of three or more turns where one speaker
  only prompts; "As you know, Bob" exchanges; exchanges that fail all
  four of Stein's questions; a dialogue scene with no physical anchor.
- §7 Information with no character who needs it now; forward-pointing
  phrases and narrator forecasts (candidates: `autonovel mechanical
  prolepsis`; a forecast passes only under a declared retrospective
  narrator and only where it sharpens the book's central question; a
  character's clairvoyance never); thought-verb thesis openers (as
  candidates).
- §7.4 Unglossed proper nouns: places, fortresses, coins, battles or
  offices named before the sentence says what they are. Quote each.
- §7.9 Said more than once: every point (a fact, a rule, a count, an
  explanation, who someone is, an earlier scene) made twice or more in
  the chapter, in any words, with its lines and the one that should
  stay; a story-so-far paragraph at the chapter's start; a description
  repeated word for word from an earlier chapter (candidates:
  `autonovel mechanical repeats`). [flag a point made three times, or a
  story-so-far opening]
- §7.3 / CRAFT §1 Spine: can the reader say, from this chapter alone,
  what the book is about and which step this chapter is? [flag a
  chapter that names no step of the book's question on a book whose
  voice file asks for it] This is a chapter-level check of the
  narration. Whether the chapters cause each other is a book-level
  test (CRAFT §1 "Causation, not sequence"; `/autonovel:structure-review`),
  and a narrator forecast passes nothing there.
- §8 Chapter ends on reflection or summary rather than the turn or a
  prompt; the same closing device two chapters running.

---

## Sources

- Bell, James Scott. *Plot & Structure* (2004); *Conflict & Suspense*
  (2011).
- Bickham, Jack M. *Scene and Structure* (1993).
- Browne, Renni, and Dave King. *Self-Editing for Fiction Writers*
  (2nd ed., 2004).
- Child, Lee. "A Simple Way to Create Suspense." *New York Times*,
  8 Dec 2012.
- Darwin, Emma. *This Itch of Writing* (Substack): "Psychic Distance:
  What It Is and How to Use It"; "Six Thoughts about Psychic Distance";
  "Ten Things That Go Wrong With Historical Fiction"; "Handclasps,
  Explosions, and Ribbons and Bows". Historia Magazine, "Information
  without it being clunkingly obvious" (2019).
- Follett, Ken. Interview, *Entrepreneur* (2020); Masterclass remarks
  collected at writerswrite.co.za.
- Gardner, John. *The Art of Fiction* (1983).
- George, Elizabeth. *Write Away* (2004).
- Gopen, George D., and Judith A. Swan. "The Science of Scientific
  Writing." *American Scientist* 78 (1990).
- Harris, Robert. Walter Scott Prize interview; Goodreads author Q&A;
  Hot Press and CSMonitor interviews.
- Hemingway, Ernest. *Death in the Afternoon* (1932).
- Hitchcock, Alfred, in François Truffaut, *Hitchcock* (1967), p. 52
  (the bomb under the table); David Bordwell, "Hitchcock, Lessing, and
  the bomb under the table" (2013).
- Ingermanson, Randy. "Writing the Perfect Scene."
  advancedfictionwriting.com.
- Le Guin, Ursula K. *Steering the Craft* (1998; rev. 2015).
- Leonard, Elmore. "Easy on the Adverbs, Exclamation Points and
  Especially Hooptedoodle." *New York Times*, 16 Jul 2001.
- Liberman, Mark. "Dialogue proportion." *Language Log*, 29 Dec 2017.
- Mantel, Hilary. *The Creative Process* interview; NPR *Fresh Air*,
  26 Nov 2012; Reith Lectures (BBC, 2017).
- McKee, Robert. *Story* (1997); "Do Your Scenes Turn?" mckeestory.com.
- Palahniuk, Chuck. "Nuts and Bolts: 'Thought' Verbs." LitReactor,
  12 Aug 2013.
- Pinker, Steven. *The Sense of Style* (2014), ch. 5.
- Prose, Francine. *Reading Like a Writer* (2006), ch. 4.
- Provost, Gary. *100 Ways to Improve Your Writing* (1985).
- Scofield, Sandra. *The Scene Book* (2007).
- Shiner, Lewis, and Bruce Sterling. "Turkey City Lexicon." SFWA.
- Spark, Muriel. *The Prime of Miss Jean Brodie* (1961).
- Stein, Sol. *Stein on Writing* (1995); *How to Grow a Novel* (1999).
- Stone, Irving. "The Biographical Novel" (lecture essay, c. 1957).
- Swain, Dwight V. *Techniques of the Selling Writer* (1965).
- Vonnegut, Kurt. *Bagombo Snuff Box* (1999), preface.
- Williams, Joseph M. *Style: Lessons in Clarity and Grace* (various
  editions).
- Wood, James. *How Fiction Works* (2008).
- *Writing Excuses* 10.25 "What Makes a Scene?" and 12.14 "Controlling
  Pacing with Structure".
