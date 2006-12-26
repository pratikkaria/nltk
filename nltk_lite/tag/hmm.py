# Natural Language Toolkit: Hidden Markov Model
#
# Copyright (C) 2001-2006 University of Pennsylvania
# Author: Trevor Cohn <tacohn@csse.unimelb.edu.au>
#         Philip Blunsom <pcbl@csse.unimelb.edu.au>
#         Tiago Tresoldi <tiago@tresoldi.pro.br> (fixes)
# URL: <http://nltk.sf.net>
# For license information, see LICENSE.TXT
#
# $Id$

"""
Hidden Markov Models (HMMs) largely used to assign the correct label sequence
to sequential data or assess the probability of a given label and data
sequence. These models are finite state machines characterised by a number of
states, transitions between these states, and output symbols emitted while in
each state. The HMM is an extension to the Markov chain, where each state
corresponds deterministically to a given event. In the HMM the observation is
a probabilistic function of the state. HMMs share the Markov chain's
assumption, being that the probability of transition from one state to another
only depends on the current state - i.e. the series of states that led to the
current state are not used. They are also time invariant.

The HMM is a directed graph, with probability weighted edges (representing the
probability of a transition between the source and sink states) where each
vertex emits an output symbol when entered. The symbol (or observation) is
non-deterministically generated. For this reason, knowing that a sequence of
output observations was generated by a given HMM does not mean that the
corresponding sequence of states (and what the current state is) is known.
This is the 'hidden' in the hidden markov model.

Formally, a HMM can be characterised by:
    - the output observation alphabet. This is the set of symbols which may be
      observed as output of the system. 
    - the set of states. 
    - the transition probabilities M{a_{ij} = P(s_t = j | s_{t-1} = i)}. These
      represent the probability of transition to each state from a given
      state. 
    - the output probability matrix M{b_i(k) = P(X_t = o_k | s_t = i)}. These
      represent the probability of observing each symbol in a given state.
    - the initial state distribution. This gives the probability of starting
      in each state.

To ground this discussion, take a common NLP application, part-of-speech (POS)
tagging. An HMM is desirable for this task as the highest probability tag
sequence can be calculated for a given sequence of word forms. This differs
from other tagging techniques which often tag each word individually, seeking
to optimise each individual tagging greedily without regard to the optimal
combination of tags for a larger unit, such as a sentence. The HMM does this
with the Viterbi algorithm, which efficiently computes the optimal path
through the graph given the sequence of words forms.

In POS tagging the states usually have a 1:1 correspondence with the tag
alphabet - i.e. each state represents a single tag. The output observation
alphabet is the set of word forms (the lexicon), and the remaining three
parameters are derived by a training regime. With this information the
probability of a given sentence can be easily derived, by simply summing the
probability of each distinct path through the model. Similarly, the highest
probability tagging sequence can be derived with the Viterbi algorithm,
yielding a state sequence which can be mapped into a tag sequence.

This discussion assumes that the HMM has been trained. This is probably the
most difficult task with the model, and requires either MLE estimates of the
parameters or unsupervised learning using the Baum-Welch algorithm, a variant
of EM.
"""

from nltk_lite.probability import *
from numpy import *
import re

# _NINF = float('-inf')  # won't work on Windows
_NINF = float('-1e300')

_TEXT = 0  # index of text in a tuple
_TAG = 1   # index of tag in a tuple

class HiddenMarkovModel(object):
    """
    Hidden Markov model class, a generative model for labelling sequence data.
    These models define the joint probability of a sequence of symbols and
    their labels (state transitions) as the product of the starting state
    probability, the probability of each state transition, and the probability
    of each observation being generated from each state. This is described in
    more detail in the module documentation.
    
    This implementation is based on the HMM description in Chapter 8, Huang,
    Acero and Hon, Spoken Language Processing.
    """
    def __init__(self, symbols, states, transitions, outputs, priors):
        """
        Creates a hidden markov model parametised by the the states,
        transition probabilities, output probabilities and priors.

        @param  symbols:        the set of output symbols (alphabet)
        @type   symbols:        (seq) of any
        @param  states:         a set of states representing state space
        @type   states:         seq of any
        @param  transitions:    transition probabilities; Pr(s_i | s_j)
                                is the probability of transition from state i
                                given the model is in state_j
        @type   transitions:    C{ConditionalProbDistI}
        @param  outputs:        output probabilities; Pr(o_k | s_i) is the
                                probability of emitting symbol k when entering
                                state i
        @type   outputs:        C{ConditionalProbDistI}
        @param  priors:         initial state distribution; Pr(s_i) is the
                                probability of starting in state i
        @type   priors:         C{ProbDistI}
        """

        self._states = states
        self._transitions = transitions
        self._symbols = symbols
        self._outputs = outputs
        self._priors = priors

    def probability(self, sequence):
        """
        Returns the probability of the given symbol sequence. If the sequence
        is labelled, then returns the joint probability of the symbol, state
        sequence. Otherwise, uses the forward algorithm to find the
        probability over all label sequences.

        @return: the probability of the sequence
        @rtype: float
        @param sequence: the sequence of symbols which must contain the TEXT
            property, and optionally the TAG property
        @type sequence:  Token
        """
        return exp(self.log_probability(sequence))

    def log_probability(self, sequence):
        """
        Returns the log-probability of the given symbol sequence. If the
        sequence is labelled, then returns the joint log-probability of the
        symbol, state sequence. Otherwise, uses the forward algorithm to find
        the log-probability over all label sequences.

        @return: the log-probability of the sequence
        @rtype: float
        @param sequence: the sequence of symbols which must contain the TEXT
            property, and optionally the TAG property
        @type sequence:  Token
        """

        T = len(sequence)
        N = len(self._states)

        if T > 0 and sequence[0][_TAG]:
            last_state = sequence[0][_TAG]
            p = self._priors.logprob(last_state) + \
                self._outputs[last_state].logprob(sequence[0][_TEXT])
            for t in range(1, T):
                state = sequence[t][_TAG]
                p += self._transitions[last_state].logprob(state) + \
                     self._outputs[state].logprob(sequence[t][_TEXT])
                last_state = state
            return p
        else:
            alpha = self._forward_probability(sequence)
            p = _log_add(*alpha[T-1, :])
            return p

    def tag(self, unlabelled_sequence):
        """
        Tags the sequence with the highest probability state sequence. This
        uses the best_path method to find the Viterbi path.

        @return: a labelled sequence of symbols
        @rtype: list
        @param unlabelled_sequence: the sequence of unlabelled symbols 
        @type unlabelled_sequence: list
        """

        path = self.best_path(unlabelled_sequence)
        for i in range(len(path)):
            unlabelled_sequence[i] = (unlabelled_sequence[i][_TEXT], path[i])
        return unlabelled_sequence

    def _output_logprob(self, state, symbol):
        """
        @return: the log probability of the symbol being observed in the given
            state
        @rtype: float
        """
        return self._outputs[state].logprob(symbol)

    def best_path(self, unlabelled_sequence):
        """
        Returns the state sequence of the optimal (most probable) path through
        the HMM. Uses the Viterbi algorithm to calculate this part by dynamic
        programming.

        @return: the state sequence
        @rtype: sequence of any
        @param unlabelled_sequence: the sequence of unlabelled symbols 
        @type unlabelled_sequence: list
        """

        T = len(unlabelled_sequence)
        N = len(self._states)
        V = zeros((T, N), float64)
        B = {}

        # find the starting log probabilities for each state
        symbol = unlabelled_sequence[0][_TEXT]
        for i, state in enumerate(self._states):
            V[0, i] = self._priors.logprob(state) + \
                      self._output_logprob(state, symbol)
            B[0, state] = None

        # find the maximum log probabilities for reaching each state at time t
        for t in range(1, T):
            symbol = unlabelled_sequence[t][_TEXT]
            for j in range(N):
                sj = self._states[j]
                best = None
                for i in range(N):
                    si = self._states[i]
                    va = V[t-1, i] + self._transitions[si].logprob(sj)
                    if not best or va > best[0]:
                        best = (va, si)
                V[t, j] = best[0] + self._output_logprob(sj, symbol)
                B[t, sj] = best[1]

        # find the highest probability final state
        best = None
        for i in range(N):
            val = V[T-1, i]
            if not best or val > best[0]:
                best = (val, self._states[i])

        # traverse the back-pointers B to find the state sequence
        current = best[1]
        sequence = [current]
        for t in range(T-1, 0, -1):
            last = B[t, current]
            sequence.append(last)
            current = last

        sequence.reverse()
        return sequence

    def random_sample(self, rng, length):
        """
        Randomly sample the HMM to generate a sentence of a given length. This
        samples the prior distribution then the observation distribution and
        transition distribution for each subsequent observation and state.
        This will mostly generate unintelligible garbage, but can provide some
        amusement.

        @return:        the randomly created state/observation sequence,
                        generated according to the HMM's probability
                        distributions. The SUBTOKENS have TEXT and TAG
                        properties containing the observation and state
                        respectively.
        @rtype:         list
        @param rng:     random number generator
        @type rng:      Random (or any object with a random() method)
        @param length:  desired output length
        @type length:   int
        """

        # sample the starting state and symbol prob dists
        tokens = []
        state = self._sample_probdist(self._priors, rng.random(), self._states)
        symbol = self._sample_probdist(self._outputs[state],
                                  rng.random(), self._symbols)
        tokens.append((symbol, state))

        for i in range(1, length):
            # sample the state transition and symbol prob dists
            state = self._sample_probdist(self._transitions[state],
                                     rng.random(), self._states)
            symbol = self._sample_probdist(self._outputs[state],
                                      rng.random(), self._symbols)
            tokens.append((symbol, state))

        return tokens

    def _sample_probdist(self, probdist, p, samples):
        cum_p = 0
        for sample in samples:
            add_p = probdist.prob(sample)
            if cum_p <= p <= cum_p + add_p:
                return sample
            cum_p += add_p
        raise Exception('Invalid probability distribution - does not sum to one')

    def entropy(self, unlabelled_sequence):
        """
        Returns the entropy over labellings of the given sequence. This is
        given by:

        H(O) = - sum_S Pr(S | O) log Pr(S | O)

        where the summation ranges over all state sequences, S. Let M{Z =
        Pr(O) = sum_S Pr(S, O)} where the summation ranges over all state
        sequences and O is the observation sequence. As such the entropy can
        be re-expressed as:

        H = - sum_S Pr(S | O) log [ Pr(S, O) / Z ]
          = log Z - sum_S Pr(S | O) log Pr(S, 0)
          = log Z - sum_S Pr(S | O) [ log Pr(S_0) + sum_t Pr(S_t | S_{t-1})
                                                  + sum_t Pr(O_t | S_t) ]
        
        The order of summation for the log terms can be flipped, allowing
        dynamic programming to be used to calculate the entropy. Specifically,
        we use the forward and backward probabilities (alpha, beta) giving:

        H = log Z - sum_s0 alpha_0(s0) beta_0(s0) / Z * log Pr(s0)
                  + sum_t,si,sj alpha_t(si) Pr(sj | si) Pr(O_t+1 | sj) beta_t(sj)
                                / Z * log Pr(sj | si)
                  + sum_t,st alpha_t(st) beta_t(st) / Z * log Pr(O_t | st)

        This simply uses alpha and beta to find the probabilities of partial
        sequences, constrained to include the given state(s) at some point in
        time.
        """

        T = len(unlabelled_sequence)
        N = len(self._states)

        alpha = self._forward_probability(unlabelled_sequence)
        beta = self._backward_probability(unlabelled_sequence)
        normalisation = _log_add(*alpha[T-1, :])

        entropy = normalisation

        # starting state, t = 0
        for i, state in enumerate(self._states):
            p = exp(alpha[0, i] + beta[0, i] - normalisation)
            entropy -= p * self._priors.logprob(state) 
            #print 'p(s_0 = %s) =' % state, p

        # state transitions
        for t0 in range(T - 1):
            t1 = t0 + 1
            for i0, s0 in enumerate(self._states):
                for i1, s1 in enumerate(self._states):
                    p = exp(alpha[t0, i0] + self._transitions[s0].logprob(s1) +
                               self._outputs[s1].logprob(unlabelled_sequence[t1][_TEXT]) + 
                               beta[t1, i1] - normalisation)
                    entropy -= p * self._transitions[s0].logprob(s1) 
                    #print 'p(s_%d = %s, s_%d = %s) =' % (t0, s0, t1, s1), p

        # symbol emissions
        for t in range(T):
            for i, state in enumerate(self._states):
                p = exp(alpha[t, i] + beta[t, i] - normalisation)
                entropy -= p * self._outputs[state].logprob(unlabelled_sequence[t][_TEXT]) 
                #print 'p(s_%d = %s) =' % (t, state), p

        return entropy

    def point_entropy(self, unlabelled_sequence):
        """
        Returns the pointwise entropy over the possible states at each
        position in the chain, given the observation sequence.
        """

        T = len(unlabelled_sequence)
        N = len(self._states)

        alpha = self._forward_probability(unlabelled_sequence)
        beta = self._backward_probability(unlabelled_sequence)
        normalisation = _log_add(*alpha[T-1, :])
    
        entropies = zeros(T, float64)
        probs = zeros(N, float64)
        for t in range(T):
            for s in range(N):
                probs[s] = alpha[t, s] + beta[t, s] - normalisation

            for s in range(N):
                entropies[t] -= exp(probs[s]) * probs[s]

        return entropies

    def _exhaustive_entropy(self, unlabelled_sequence):
        T = len(unlabelled_sequence)
        N = len(self._states)

        labellings = [[state] for state in self._states]
        for t in range(T - 1):
            current = labellings
            labellings = []
            for labelling in current:
                for state in self._states:
                    labellings.append(labelling + [state])

        log_probs = []
        for labelling in labellings:
            labelled_sequence = unlabelled_sequence[:]
            for t, label in enumerate(labelling):
                labelled_sequence[t] = (labelled_sequence[t][_TEXT], label)
            lp = self.log_probability(labelled_sequence)
            log_probs.append(lp)
        normalisation = _log_add(*log_probs)

        #ps = zeros((T, N), float64)
        #for labelling, lp in zip(labellings, log_probs):
            #for t in range(T):
                #ps[t, self._states.index(labelling[t])] += exp(lp - normalisation)

        #for t in range(T):
            #print 'prob[%d] =' % t, ps[t]

        entropy = 0
        for lp in log_probs:
            lp -= normalisation
            entropy -= exp(lp) * lp

        return entropy

    def _exhaustive_point_entropy(self, unlabelled_sequence):
        T = len(unlabelled_sequence)
        N = len(self._states)

        labellings = [[state] for state in self._states]
        for t in range(T - 1):
            current = labellings
            labellings = []
            for labelling in current:
                for state in self._states:
                    labellings.append(labelling + [state])

        log_probs = []
        for labelling in labellings:
            labelled_sequence = unlabelled_sequence[:]
            for t, label in enumerate(labelling):
                labelled_sequence[t] = (labelled_sequence[t][_TEXT], label)
            lp = self.log_probability(labelled_sequence)
            log_probs.append(lp)

        normalisation = _log_add(*log_probs)

        probabilities = zeros((T, N), float64)
        probabilities[:] = _NINF
        for labelling, lp in zip(labellings, log_probs):
            lp -= normalisation
            for t, label in enumerate(labelling):
                index = self._states.index(label)
                probabilities[t, index] = _log_add(probabilities[t, index], lp)

        entropies = zeros(T, float64)
        for t in range(T):
            for s in range(N):
                entropies[t] -= exp(probabilities[t, s]) * probabilities[t, s]

        return entropies

    def _forward_probability(self, unlabelled_sequence):
        """
        Return the forward probability matrix, a T by N array of
        log-probabilities, where T is the length of the sequence and N is the
        number of states. Each entry (t, s) gives the probability of being in
        state s at time t after observing the partial symbol sequence up to
        and including t.

        @return: the forward log probability matrix
        @rtype:  array
        @param unlabelled_sequence: the sequence of unlabelled symbols 
        @type unlabelled_sequence: list
        """
        T = len(unlabelled_sequence)
        N = len(self._states)
        alpha = zeros((T, N), float64)

        symbol = unlabelled_sequence[0][_TEXT]
        for i, state in enumerate(self._states):
            alpha[0, i] = self._priors.logprob(state) + \
                          self._outputs[state].logprob(symbol)

        for t in range(1, T):
            symbol = unlabelled_sequence[t][_TEXT]
            for i, si in enumerate(self._states):
                alpha[t, i] = _NINF
                for j, sj in enumerate(self._states):
                    alpha[t, i] = _log_add(alpha[t, i], alpha[t-1, j] +
                                           self._transitions[sj].logprob(si))
                alpha[t, i] += self._outputs[si].logprob(symbol)


        return alpha

    def _backward_probability(self, unlabelled_sequence):
        """
        Return the backward probability matrix, a T by N array of
        log-probabilities, where T is the length of the sequence and N is the
        number of states. Each entry (t, s) gives the probability of being in
        state s at time t after observing the partial symbol sequence from t
        .. T.

        @return: the backward log probability matrix
        @rtype:  array
        @param unlabelled_sequence: the sequence of unlabelled symbols 
        @type unlabelled_sequence: list
        """
        T = len(unlabelled_sequence)
        N = len(self._states)
        beta = zeros((T, N), float64)

        # initialise the backward values
        beta[T-1, :] = log(1)

        # inductively calculate remaining backward values
        for t in range(T-2, -1, -1):
            symbol = unlabelled_sequence[t+1][_TEXT]
            for i, si in enumerate(self._states):
                beta[t, i] = _NINF
                for j, sj in enumerate(self._states):
                    beta[t, i] = _log_add(beta[t, i],
                                          self._transitions[si].logprob(sj) + 
                                          self._outputs[sj].logprob(symbol) + 
                                          beta[t + 1, j])

        return beta

    def __repr__(self):
        return '<HiddenMarkovModel %d states and %d output symbols>' \
                % (len(self._states), len(self._symbols))

class HiddenMarkovModelTrainer(object):
    """
    Algorithms for learning HMM parameters from training data. These include
    both supervised learning (MLE) and unsupervised learning (Baum-Welch).
    """
    def __init__(self, states=None, symbols=None):
        """
        Creates an HMM trainer to induce an HMM with the given states and
        output symbol alphabet. A supervised and unsupervised training
        method may be used. If either of the states or symbols are not given,
        these may be derived from supervised training.

        @param states:  the set of state labels
        @type states:   sequence of any
        @param symbols: the set of observation symbols
        @type symbols:  sequence of any
        """
        if states:
            self._states = states
        else:
            self._states = []
        if symbols:
            self._symbols = symbols
        else:
            self._symbols = []

    def train(self, labelled_sequences=None, unlabelled_sequences=None,
              **kwargs):
        """
        Trains the HMM using both (or either of) supervised and unsupervised
        techniques.

        @return: the trained model
        @rtype: HiddenMarkovModel
        @param labelled_sequences: the supervised training data, a set of
            labelled sequences of observations
        @type labelled_sequences: list
        @param unlabelled_sequences: the unsupervised training data, a set of
            sequences of observations
        @type unlabelled_sequences: list
        @param kwargs: additional arguments to pass to the training methods
        """
        assert labelled_sequences or unlabelled_sequences
        model = None
        if labelled_sequences:
            model = self.train_supervised(labelled_sequences, **kwargs)
        if unlabelled_sequences:
            if model: kwargs['model'] = model
            model = self.train_unsupervised(unlabelled_sequences, **kwargs)
        return model

    def train_unsupervised(self, unlabelled_sequences, **kwargs):
        """
        Trains the HMM using the Baum-Welch algorithm to maximise the
        probability of the data sequence. This is a variant of the EM
        algorithm, and is unsupervised in that it doesn't need the state
        sequences for the symbols. The code is based on 'A Tutorial on Hidden
        Markov Models and Selected Applications in Speech Recognition',
        Lawrence Rabiner, IEEE, 1989.

        @return: the trained model
        @rtype: HiddenMarkovModel
        @param unlabelled_sequences: the training data, a set of
            sequences of observations
        @type unlabelled_sequences: list
        @param kwargs: may include the following parameters::
            model - a HiddenMarkovModel instance used to begin the Baum-Welch
                algorithm
            max_iterations - the maximum number of EM iterations
            convergence_logprob - the maximum change in log probability to
                allow convergence
        """

        N = len(self._states)
        M = len(self._symbols)
        symbol_dict = dict((self._symbols[i], i) for i in range(M))

        # create a uniform HMM, which will be iteratively refined, unless
        # given an existing model
        model = kwargs.get('model')
        if not model:
            priors = UniformProbDist(self._states)
            transitions = DictionaryConditionalProbDist(
                            dict((state, UniformProbDist(self._states))
                                  for state in self._states))
            output = DictionaryConditionalProbDist(
                            dict((state, UniformProbDist(self._symbols))
                                  for state in self._states))
            model = HiddenMarkovModel(self._symbols, self._states, 
                            transitions, output, priors)

        # update model prob dists so that they can be modified
        model._priors = MutableProbDist(model._priors, self._states)
        model._transitions = DictionaryConditionalProbDist(
            dict((s, MutableProbDist(model._transitions[s], self._states))
                 for s in self._states))
        model._outputs = DictionaryConditionalProbDist(
            dict((s, MutableProbDist(model._outputs[s], self._symbols))
                 for s in self._states))

        # iterate until convergence
        converged = False
        last_logprob = None
        iteration = 0
        max_iterations = kwargs.get('max_iterations', 1000)
        epsilon = kwargs.get('convergence_logprob', 1e-6)
        while not converged and iteration < max_iterations:
            A_numer = ones((N, N), float64) * _NINF
            B_numer = ones((N, M), float64) * _NINF
            A_denom = ones(N, float64) * _NINF
            B_denom = ones(N, float64) * _NINF

            logprob = 0
            for sequence in unlabelled_sequences:
                # compute forward and backward probabilities
                alpha = model._forward_probability(sequence)
                beta = model._backward_probability(sequence)

                # find the log probability of the sequence
                T = len(sequence)
                lpk = _log_add(*alpha[T-1, :])
                logprob += lpk

                # now update A and B (transition and output probabilities)
                # using the alpha and beta values. Please refer to Rabiner's
                # paper for details, it's too hard to explain in comments
                local_A_numer = ones((N, N), float64) * _NINF
                local_B_numer = ones((N, M), float64) * _NINF
                local_A_denom = ones(N, float64) * _NINF
                local_B_denom = ones(N, float64) * _NINF

                # for each position, accumulate sums for A and B
                for t in range(T):
                    x = sequence[t][_TEXT] #not found? FIXME
                    if t < T - 1:
                        xnext = sequence[t+1][_TEXT] #not found? FIXME
                    xi = symbol_dict[x]
                    for i in range(N):
                        si = self._states[i]
                        if t < T - 1:
                            for j in range(N):
                                sj = self._states[j]
                                local_A_numer[i, j] =  \
                                    _log_add(local_A_numer[i, j],
                                        alpha[t, i] + 
                                        model._transitions[si].logprob(sj) + 
                                        model._outputs[sj].logprob(xnext) +
                                        beta[t+1, j])
                            local_A_denom[i] = _log_add(local_A_denom[i],
                                alpha[t, i] + beta[t, i])
                        else:
                            local_B_denom[i] = _log_add(local_A_denom[i],
                                alpha[t, i] + beta[t, i])

                        local_B_numer[i, xi] = _log_add(local_B_numer[i, xi],
                            alpha[t, i] + beta[t, i])

                # add these sums to the global A and B values
                for i in range(N):
                    for j in range(N):
                        A_numer[i, j] = _log_add(A_numer[i, j],
                                                local_A_numer[i, j] - lpk)
                    for k in range(M):
                        B_numer[i, k] = _log_add(B_numer[i, k],
                                                local_B_numer[i, k] - lpk)

                    A_denom[i] = _log_add(A_denom[i], local_A_denom[i] - lpk)
                    B_denom[i] = _log_add(B_denom[i], local_B_denom[i] - lpk)

            # use the calculated values to update the transition and output
            # probability values
            for i in range(N):
                si = self._states[i]
                for j in range(N):
                    sj = self._states[j]
                    model._transitions[si].update(sj, A_numer[i,j] - A_denom[i])
                for k in range(M):
                    ok = self._symbols[k]
                    model._outputs[si].update(ok, B_numer[i,k] - B_denom[i])
                # Rabiner says the priors don't need to be updated. I don't
                # believe him. FIXME

            # test for convergence
            if iteration > 0 and abs(logprob - last_logprob) < epsilon:
                converged = True

            print 'iteration', iteration, 'logprob', logprob
            iteration += 1
            last_logprob = logprob

        return model

    def train_supervised(self, labelled_sequences, **kwargs):
        """
        Supervised training maximising the joint probability of the symbol and
        state sequences. This is done via collecting frequencies of
        transitions between states, symbol observations while within each
        state and which states start a sentence. These frequency distributions
        are then normalised into probability estimates, which can be
        smoothed if desired.

        @return: the trained model
        @rtype: HiddenMarkovModel
        @param labelled_sequences: the training data, a set of
            labelled sequences of observations
        @type labelled_sequences: list
        @param kwargs: may include an 'estimator' parameter, a function taking
            a C{FreqDist} and a number of bins and returning a C{ProbDistI};
            otherwise a MLE estimate is used
        """

        # default to the MLE estimate
        estimator = kwargs.get('estimator')
        if estimator == None:
            estimator = lambda fdist, bins: MLEProbDist(fdist)

        # count occurences of starting states, transitions out of each state
        # and output symbols observed in each state
        starting = FreqDist()
        transitions = ConditionalFreqDist()
        outputs = ConditionalFreqDist()
        for sequence in labelled_sequences:
            lasts = None
            for token in sequence:
                state = token[_TAG]
                symbol = token[_TEXT]
                if lasts == None:
                    starting.inc(state)
                else:
                    transitions[lasts].inc(state)
                outputs[state].inc(symbol)
                lasts = state

                # update the state and symbol lists
                if state not in self._states:
                    self._states.append(state)
                if symbol not in self._symbols:
                    self._symbols.append(symbol)

        # create probability distributions (with smoothing)
        N = len(self._states)
        pi = estimator(starting, N)
        A = ConditionalProbDist(transitions, estimator, False, N)
        B = ConditionalProbDist(outputs, estimator, False, len(self._symbols))
                               
        return HiddenMarkovModel(self._symbols, self._states, A, B, pi)

def _log_add(*values):
    """
    Adds the logged values, returning the logarithm of the addition.
    """
    x = max(values)
    if x > _NINF:
        sum_diffs = 0
        for value in values:
            sum_diffs += exp(value - x)
        return x + log(sum_diffs)
    else:
        return x

def demo():
    # demonstrates HMM probability calculation

    print
    print "HMM probability calculation demo"
    print

    # example taken from page 381, Huang et al
    symbols = ['up', 'down', 'unchanged']
    states = ['bull', 'bear', 'static']

    def pd(values, samples):
        d = {}
        for value, item in zip(values, samples):
            d[item] = value
        return DictionaryProbDist(d)

    def cpd(array, conditions, samples):
        d = {}
        for values, condition in zip(array, conditions):
            d[condition] = pd(values, samples)
        return DictionaryConditionalProbDist(d)

    A = array([[0.6, 0.2, 0.2], [0.5, 0.3, 0.2], [0.4, 0.1, 0.5]], float64)
    A = cpd(A, states, states)
    B = array([[0.7, 0.1, 0.2], [0.1, 0.6, 0.3], [0.3, 0.3, 0.4]], float64)
    B = cpd(B, states, symbols)
    pi = array([0.5, 0.2, 0.3], float64)
    pi = pd(pi, states)

    model = HiddenMarkovModel(symbols=symbols, states=states,
                              transitions=A, outputs=B, priors=pi)

    print 'Testing', model

    for test in [['up', 'up'], ['up', 'down', 'up'],
                 ['down'] * 5, ['unchanged'] * 5 + ['up']]:

        sequence = [(t, None) for t in test]

        print 'Testing with state sequence', test
        print 'probability =', model.probability(sequence)
        print 'tagging =    ', model.tag(sequence)
        print 'p(tagged) =  ', model.probability(sequence)
        print 'H =          ', model.entropy(sequence)
        print 'H_exh =      ', model._exhaustive_entropy(sequence)
        print 'H(point) =   ', model.point_entropy(sequence)
        print 'H_exh(point)=', model._exhaustive_point_entropy(sequence)
        print


def load_pos(num_sents):
    from nltk_lite.corpora import brown
    from itertools import islice

    sentences = list(islice(brown.tagged(), num_sents))

    tag_set = ["'", "''", '(', ')', '*', ',', '.', ':', '--', '``', 'abl',
        'abn', 'abx', 'ap', 'ap$', 'at', 'be', 'bed', 'bedz', 'beg', 'bem',
        'ben', 'ber', 'bez', 'cc', 'cd', 'cd$', 'cs', 'do', 'dod', 'doz',
        'dt', 'dt$', 'dti', 'dts', 'dtx', 'ex', 'fw', 'hv', 'hvd', 'hvg',
        'hvn', 'hvz', 'in', 'jj', 'jjr', 'jjs', 'jjt', 'md', 'nn', 'nn$',
        'nns', 'nns$', 'np', 'np$', 'nps', 'nps$', 'nr', 'nr$', 'od', 'pn',
        'pn$', 'pp$', 'ppl', 'ppls', 'ppo', 'pps', 'ppss', 'ql', 'qlp', 'rb',
        'rb$', 'rbr', 'rbt', 'rp', 'to', 'uh', 'vb', 'vbd', 'vbg', 'vbn',
        'vbz', 'wdt', 'wp$', 'wpo', 'wps', 'wql', 'wrb']
        
    sequences = []
    sequence = []
    symbols = set()
    start_re = re.compile(r'[^-*+]*')
    for sentence in sentences:
        for i in range(len(sentence)):
            word, tag = sentence[i]
            word = word.lower()  # normalize
            symbols.add(word)    # log this word
            m = start_re.match(tag)
            # cleanup the tag
            tag = m.group(0)
            if tag not in tag_set:
                tag = '*'
            sentence[i] = (word, tag)  # store cleaned-up tagged token

    return sentences, tag_set, list(symbols)

def test_pos(model, sentences, display=False):
    from sys import stdout

    count = correct = 0
    for sentence in sentences:
        sentence = [(token[0], None) for token in sentence]
        pts = model.best_path(sentence)
        if display:
            print sentence
            print 'HMM >>>'
            print pts
            print model.entropy(sentences)
            print '-' * 60
        else:
            print '\b.',
            stdout.flush()
        for token, tag in zip(sentence, pts):
            count += 1
            if tag == token[_TAG]:
                correct += 1

    print 'accuracy over', count, 'tokens %.1f' % (100.0 * correct / count)

def demo_pos():
    # demonstrates POS tagging using supervised training

    print
    print "HMM POS tagging demo"
    print

    print 'Training HMM...'
    labelled_sequences, tag_set, symbols = load_pos(200)
    trainer = HiddenMarkovModelTrainer(tag_set, symbols)
    hmm = trainer.train_supervised(labelled_sequences[100:],
                    estimator=lambda fd, bins: LidstoneProbDist(fd, 0.1, bins))

    print 'Testing...'
    test_pos(hmm, labelled_sequences[:100], True)

def _untag(sentences):
    unlabelled = []
    for sentence in sentences:
        unlabelled.append((token[0], None) for token in sentence)
    return unlabelled

def demo_pos_bw():
    # demonstrates the Baum-Welch algorithm in POS tagging

    print
    print "Baum-Welch demo for POS tagging"
    print

    print 'Training HMM (supervised)...'
    sentences, tag_set, symbols = load_pos(310)
    symbols = set()
    for sentence in sentences:
        for token in sentence:
            symbols.add(token[_TEXT])
            
    trainer = HiddenMarkovModelTrainer(tag_set, list(symbols))
    hmm = trainer.train_supervised(sentences[100:300],
                    estimator=lambda fd, bins: LidstoneProbDist(fd, 0.1, bins))
    print 'Training (unsupervised)...'
    # it's rather slow - so only use 10 samples
    unlabelled = _untag(sentences[300:310])
    hmm = trainer.train_unsupervised(unlabelled, model=hmm, max_iterations=5)
    test_pos(hmm, sentences[:100], True)

def demo_bw():
    # demo Baum Welch by generating some sequences and then performing
    # unsupervised training on them

    print
    print "Baum-Welch demo for market example"
    print

    # example taken from page 381, Huang et al
    symbols = ['up', 'down', 'unchanged']
    states = ['bull', 'bear', 'static']

    def pd(values, samples):
        d = {}
        for value, item in zip(values, samples):
            d[item] = value
        return DictionaryProbDist(d)

    def cpd(array, conditions, samples):
        d = {}
        for values, condition in zip(array, conditions):
            d[condition] = pd(values, samples)
        return DictionaryConditionalProbDist(d)

    A = array([[0.6, 0.2, 0.2], [0.5, 0.3, 0.2], [0.4, 0.1, 0.5]], float64)
    A = cpd(A, states, states)
    B = array([[0.7, 0.1, 0.2], [0.1, 0.6, 0.3], [0.3, 0.3, 0.4]], float64)
    B = cpd(B, states, symbols)
    pi = array([0.5, 0.2, 0.3], float64)
    pi = pd(pi, states)

    model = HiddenMarkovModel(symbols=symbols, states=states,
                              transitions=A, outputs=B, priors=pi)

    # generate some random sequences
    training = []
    import random
    rng = random.Random()
    for i in range(10):
        item = model.random_sample(rng, 5)
        training.append((i[0], None) for i in item)

    # train on those examples, starting with the model that generated them
    trainer = HiddenMarkovModelTrainer(states, symbols)
    hmm = trainer.train_unsupervised(training, model=model, max_iterations=1000)
    
if __name__ == '__main__':
    demo()
    demo_pos()
    demo_pos_bw()
#    demo_bw()

