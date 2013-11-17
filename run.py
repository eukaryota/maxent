#!/usr/bin/python
# vim: set file-encoding=utf-8:

import sys
import math
import itertools
import operator
import cPickle
import re

import maxent

from collections import defaultdict
from maxent import MaxentModel
from optparse import OptionParser

# |iterable| should yield lines.
def read_sentences(iterable):
    sentence = []
    for line in iterable:
        columns = line.rstrip().split()
        if len(columns) == 0 and len(sentence) > 0:
            yield sentence
            sentence = []
        if len(columns) > 0:
            sentence.append(columns)
    if len(sentence) > 0:
        yield sentence

# Computes (local) features for word at position |i| given that label for word
# at position |i - 1| is |previous_label|. You can pass any additional data
# via |data| argument.
MIN_WORD_FREQUENCY = 3
MIN_LABEL_FREQUENCY = 1

#FUNCTION_WORDS = ['de', 'het', 'een', 'la', 'el', 'un', 'los']

def compute_features(data, words, poses, i, previous_label):
    # Condition on previous label.
    if previous_label != "O":
        yield "label-previous={0}".format(previous_label)

    yield "prev_pos={0}".format(poses[i - 1] if i >= 1 else "^");
    yield "prevprev_pos={0}".format(poses[i - 2] if i >= 2 else "^");

    if (previous_label == '^'):
        if (i < len(words) - 1):
            yield "next-pos={0}".format(poses[i + 1]) 
            yield "next-first-letter-up={0}".format(words[i + 1][0].isupper());
            yield "next-word={0}".format(words[i + 1].lower());

        #if (i + 3 < len(words)) and (not words[i + 1][0].isupper()) and (not words[i + 2][0].isupper()) and (words[i + 3][0].isupper()):
        #    yield "very_long_sequence.{0}.{1}".format(words[i + 1], words[i + 2])            
        #elif (i + 2 < len(words)) and (not words[i + 1][0].isupper()) and (words[i + 2][0].isupper()):
        #    yield "long_sequence.{0}".format(words[i + 1])

    #if i > 0 and poses[i - 1] == Punc:
    #    yield "label-previous={0}".format(previous_label)
    
    #yield "next-pos={0}".format(poses[i + 1] if i < len(poses) - 1 else "^");
    #yield "nextnext-pos={0}".format(poses[i + 2] if i < len(poses) - 2 else "^");

    #yield "prefix-word={0}".format("president" in words[i - 1].lower())

    word = words[i]
    if word.endswith("zee") or word.endswith("stad") or word.endswith("burg") or word.endswith("burgh"):
        yield "was-labelled-as={0}".format("I-LOC" if previous_label[0] == "B" else "B-LOC")

    #print words[i]
    if data["word_frequencies"].get(words[i], 0) >= MIN_WORD_FREQUENCY:
        yield "word-current={0}".format(words[i])
        #yield "word-len={0}".format(len(words[i]));
        yield "word-prefix3={0}".format(words[i][:3]); #not work for spanish, good for dutch

    yield "word-is-article={0}".format(poses[i] == 'DA' or poses[i] == 'Art' or poses[i] == 'Prep');
    #yield "word-is-punc={0}".format(poses[i] == 'Punc');

    yield "first-word={0}".format(i == 0);
    yield "first-letter-up={0}".format(words[i][0].isupper());
    yield "word-letter-lower={0}".format(words[i][0].islower()); #not work for spanish, good for dutch

    yield "word-has-up={0}".format(re.match(r".*[A-Z]", words[i]) != None);

    yield "word-up={0}".format(words[i] == words[i].upper());
    yield "word-lower={0}".format(words[i] == words[i].lower());

    yield "word-is-digit={0}".format(words[i].isdigit());
    #yield "word-is-alnum={0}".format(words[i].isalnum());
    yield "word-is-alpha={0}".format(words[i].isalpha());
    yield "word-has-digit={0}".format(re.match(r".*\d", words[i]) != None);
    #yield "word-has-point={0}".format(re.match(r".*[,|.]", words[i]) != None);

    #if i >= 1 and (words[i-1].lower() == "monseñor" or  words[i-1].lower() == "monseñora"):
    #    yield "prefix-name=True";
    #else:
    #    yield "prefix-name=False"

    labels = data["labelled_words"].get(words[i], dict())
    labels = filter(lambda item: item[1] > MIN_LABEL_FREQUENCY, labels.items())
    for label in labels:
        yield "was-labelled-as={0}".format(label)


    yield "current-pos={0}".format(poses[i]); #not work for spanish, good for dutch
    pos = data["posed_words"].get(words[i], dict())
    if len(pos) == 0:
        yield "max-pos-current={0}".format(0)
    else:
        yield "max-pos-current={0}".format(max(pos))

# |iterable| should yield sentences.
# |iterable| should support multiple passes.
def train_model(options, iterable):
    model = MaxentModel()
    data = {}

    data["feature_set"] = set()
    data["word_frequencies"] = defaultdict(long)
    # XXX(sandello): defaultdict(lambda: defaultdict(long)) would be
    # a better choice here (for |labelled_words|) but it could not be pickled.
    # C'est la vie.
    data["labelled_words"] = dict()
    data["posed_words"] = dict()

    print >>sys.stderr, "*** Training options are:"
    print >>sys.stderr, "   ", options

    print >>sys.stderr, "*** First pass: Computing statistics..."
    for n, sentence in enumerate(iterable):
        if (n % 1000) == 0:
            print >>sys.stderr, "   {0:6d} sentences...".format(n)
        for word, pos, label in sentence:
            data["word_frequencies"][word] += 1
            if label.startswith("B-") or label.startswith("I-"):
                if word not in data["labelled_words"]:
                    data["labelled_words"][word] = defaultdict(long)
                data["labelled_words"][word][label] += 1

            if word not in data["posed_words"]:
                data["posed_words"][word] = defaultdict(long)
            data["posed_words"][word][pos] += 1

    print >>sys.stderr, "*** Second pass: Collecting features..."
    model.begin_add_event()
    for n, sentence in enumerate(iterable):
        if (n % 1000) == 0:
            print >>sys.stderr, "   {0:6d} sentences...".format(n)
        words, poses, labels = map(list, zip(*sentence))
        for i in xrange(len(labels)):
            features = compute_features(data, words, poses, i, labels[i - 1] if i >= 1 else "^")
            features = list(features)
            model.add_event(features, labels[i])
            for feature in features:
                data["feature_set"].add(feature)
    model.end_add_event(options.cutoff)
    print >>sys.stderr, "*** Collected {0} features.".format(len(data["feature_set"]))

    print >>sys.stderr, "*** Training..."
    maxent.set_verbose(1)
    model.train(options.iterations, options.technique, options.gaussian)
    maxent.set_verbose(0)

    print >>sys.stderr, "*** Saving..."
    model.save(options.model + ".maxent")
    with open(options.model + ".data", "w") as handle:
        cPickle.dump(data, handle)

# |iterable| should yield sentences.
def eval_model(options, iterable):
    model = MaxentModel()
    data = {}

    print >>sys.stderr, "*** Loading..."
    model.load(options.model + ".maxent")
    with open(options.model + ".data", "r") as handle:
        data = cPickle.load(handle)

    print >>sys.stderr, "*** Evaluating..."
    for n, sentence in enumerate(iterable):
        if (n % 100) == 0:
            print >>sys.stderr, "   {0:6d} sentences...".format(n)
        words, poses = map(list, zip(*sentence))
        labels = eval_model_sentence(options, data, model, words, poses)

        for word, pos, label in zip(words, poses, labels):
            print label
        print

# This is a helper method for |eval_model_sentence| and, actually,
# an implementation of Viterbi algorithm.
def eval_model_sentence(options, data, model, words, poses):
    viterbi_layers = [ None for i in xrange(len(words)) ]
    viterbi_backpointers = [ None for i in xrange(len(words) + 1) ]

    # Compute first layer directly.
    viterbi_layers[0] = model.eval_all(list(compute_features(data, words, poses, 0, "^")))
    viterbi_layers[0] = dict( (k, math.log(v)) for k, v in viterbi_layers[0] )
    viterbi_backpointers[0] = dict( (k, None) for k, v in viterbi_layers[0].iteritems() )

    # Compute intermediate layers.
    for i in xrange(1, len(words)):
        viterbi_layers[i] = defaultdict(lambda: float("-inf"))
        viterbi_backpointers[i] = defaultdict(lambda: None)
        for prev_label, prev_logprob in viterbi_layers[i - 1].iteritems():
            features = compute_features(data, words, poses, i, prev_label)
            features = list(features)
            for label, prob in model.eval_all(features):
                logprob = math.log(prob)
                if prev_logprob + logprob > viterbi_layers[i][label]:
                    viterbi_layers[i][label] = prev_logprob + logprob
                    viterbi_backpointers[i][label] = prev_label

    # Most probable endpoint.
    max_logprob = float("-inf")
    max_label = None
    for label, logprob in viterbi_layers[len(words) - 1].iteritems():
        if logprob > max_logprob:
            max_logprob = logprob
            max_label = label

    # Most probable sequence.
    path = []
    label = max_label
    for i in reversed(xrange(len(words))):
        path.insert(0, label)
        label = viterbi_backpointers[i][label]

    return path

################################################################################

def main():
    parser = OptionParser("A sample MEMM model for NER")
    parser.add_option("-T", "--train", action="store_true", dest="train",
        help="Do the training, if specified; do the evaluation otherwise")
    parser.add_option("-f", "--file", type="string", dest="filename",
        metavar="FILE", help="File with the training data")
    parser.add_option("-m", "--model", type="string", dest="model",
        metavar="FILE", help="File with the model")
    parser.add_option("-c", "--cutoff", type="int", default=5, dest="cutoff",
        metavar="C", help="Event frequency cutoff during training")
    parser.add_option("-i", "--iterations", type="int", default=100, dest="iterations",
        metavar="N", help="Number of training iterations")
    parser.add_option("-g", "--gaussian", type="float", default=0.0, dest="gaussian",
        metavar="G", help="Gaussian smoothing penalty (sigma)")
    parser.add_option("-t", "--technique", type="string", default="gis", dest="technique",
        metavar="T", help="Training algorithm (either 'gis' or 'lbfgs')")
    (options, args) = parser.parse_args()

    if not options.filename:
        parser.print_help()
        sys.exit(1)

    with open(options.filename, "r") as handle:
        data = list(read_sentences(handle))

    if options.train:
        print >>sys.stderr, "*** Training model..."
        train_model(options, data)
    else:
        print >>sys.stderr, "*** Evaluating model..."
        eval_model(options, data)

    print >>sys.stderr, "*** Done!"

if __name__ == "__main__":
    main()

