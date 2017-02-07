from gensim.models import Doc2Vec
try:
    from .base import RetriEvalMixin, Matching
except SystemError:
    from base import RetriEvalMixin, Matching
# from .word2vec import filter_vocab
from gensim.models.doc2vec import TaggedDocument
from sklearn.base import BaseEstimator
from sklearn.neighbors import NearestNeighbors


class Doc2VecRetrieval(BaseEstimator, RetriEvalMixin):
    def __init__(self,
                 analyzer=None, matching=None,
                 name=None,
                 verbose=0,
                 n_epochs=10,
                 alpha=0.25,
                 min_alpha=0.05,
                 n_jobs=4,
                 **kwargs):
        # self.model = model
        self.alpha = alpha
        self.min_alpha = min_alpha
        self.verbose = verbose
        if name is None:
            name = "paragraph-vectors"

        if matching is True:
            self._matching = Matching()
        elif matching is False:
            self._matching = None
        else:
            self._matching = Matching(**dict(matching))

        self.analyzer = analyzer
        self.model = Doc2Vec(alpha=alpha,
                             min_alpha=alpha,
                             size=500,
                             window=8,
                             min_count=1,
                             sample=1e-5,
                             workers=n_jobs,
                             negative=20,
                             dm=0, dbow_words=1,  # words only with dm!=0?
                             dm_mean=0,  # unused when in concat mode
                             dm_concat=1,
                             dm_tag_count=1
                             )
        self.n_epochs = n_epochs
        self._neighbors = NearestNeighbors(**kwargs)

    def fit(self, docs, y):
        self._fit(docs, y)
        assert len(docs) == len(y)
        model = self.model
        n_epochs = self.n_epochs
        verbose = self.verbose
        decay = (self.alpha - self.min_alpha) / n_epochs
        X = [TaggedDocument(self.analyzer(doc), [label])
             for doc, label in zip(docs, y)]

        if verbose > 0:
            print("First 3 tagged documents:\n", X[:3])
            print("Training doc2vec model")
        # d2v = Doc2Vec()
        # d2v.build_vocab(X)
        # if self.intersect is not None:
        #     d2v.intersect_word2vec_format(self.intersect)
        model.build_vocab(X)
        for epoch in range(n_epochs):
            if verbose:
                print("Doc2Vec: Epoch {} of {}.".format(epoch + 1, n_epochs))
            model.train(X)
            model.alpha -= decay  # apply global decay
            model.min_alpha = model.alpha  # but no decay inside one epoch

        if verbose > 0:
            print("Finished.")
            print("model:", self.model)
            print("Shape of docvecs", model.docvecs.shape)

        if self._matching:
            self._matching.fit(docs)
        else:
            # if we dont do matching, its enough to fit a nearest neighbors on
            # all centroids before query time
            self._neighbors.fit(model.docvecs)

        self._y = y

        return self

    def query(self, query, k=None):
        model, matching = self.model, self._matching
        nn, analyze = self._neighbors, self.analyzer
        verbose = self.verbose
        if k is None:
            k = len(self._centroids)
        if matching:
            matched = matching.predict(query)
            dvs, labels = self.model.docvecs[matched], self._y[matched]
            n_ret = min(k, len(matched))
            nn.fit(dvs)
        else:
            labels = self._y
            n_ret = k
            # NearestNeighbors are already fit

        if verbose > 0:
            print(len(labels), "documents matched.")
        q = analyze(query)
        qv = model.infer_vector(q).reshape(1, -1)
        ind = nn.kneighbors(qv, n_neighbors=n_ret, return_distance=False)[0]
        y = labels[ind]
        return y
