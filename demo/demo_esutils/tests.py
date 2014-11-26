from django.test import TestCase
from elasticutils import F

from demo_esutils.models import Category
from demo_esutils.models import Article
from demo_esutils.models import User
from demo_esutils.mappings import ArticleMappingType as M
from django_esutils.filters import ElasticutilsFilterSet
from django_esutils.filters import ElasticutilsFilterBackend


class BaseTest(TestCase):
    fixtures = ['test_data']

    def setUp(self):
        self.louise = User.objects.get(pk=2)
        self.florent = User.objects.get(pk=1)
        self. search_fields = ['author.username',
                               'author.email',
                               'category_id',
                               'category.name',
                               'created_at',
                               'subject',
                               'content',
                               'status',
                               'contributors']
        self.mapping_type = M
        M.update_mapping()
        M.run_index_all()
        M.refresh_index()

    def tearDown(self):
        User.objects.all().delete()
        Category.objects.all().delete()
        Article.objects.all().delete()
        M.refresh_index()


class MappingTestCase(BaseTest):

    def test_index(self):

        # keep previous indexed objec count
        prev_count = M.count()

        # create an article
        category = Category.objects.create(name='The Tests')

        article1 = Article()
        article1.author = self.florent
        article1.category = category
        article1.content = '!'
        article1.subject = 'make it works'

        article2 = Article()
        article2.author = self.louise
        article2.category = category
        article2.content = 'yo'
        article2.subject = 'My amazing article'

        for i, art in enumerate([article1, article2]):
            # save
            art.save()
            # refresh index
            M.refresh_index()
            # check added
            add_count = M.count()
            self.assertEqual(add_count, prev_count + i + 1)

        for i, a in enumerate([article1, article2]):
            # remove an article
            a.delete()
            # refresh index
            M.refresh_index()
            # check removed
            del_count = M.count()
            self.assertEqual(del_count, add_count - i - 1)

    def test_queryset_update(self):
        # update some contents
        self.assertEqual(M.query(subject__prefix='amaz').count(), 1)
        Article.objects.filter(pk=3).update(subject='hey #tgif')

        # reindex all
        M.run_index_all()
        # refresh index
        M.refresh_index()

        # should
        self.assertEqual(M.query(subject__prefix='amaz').count(), 0)
        self.assertEqual(M.query(subject__match='#tgif').count(), 1)

        # update some contents
        self.assertEqual(M.query(content__term='yo').count(), 1)
        Article.objects.filter(pk=3).update(content='monday uh!')

        # refresh index
        M.refresh_index()

        self.assertEqual(M.query(content__term='yo').count(), 0)
        self.assertEqual(M.query(content__term='monday').count(), 1)

    def test_query_string(self):

        self.assertEqual(M.query(subject__match='WorkS').count(), 1)
        self.assertEqual(M.query(subject__match='works').count(), 1)
        self.assertEqual(M.query(subject__prefix='amaz').count(), 1)
        self.assertEqual(M.query(subject__match='amaz').count(), 0)

        self.assertEqual(M.query(**{'author.username__prefix': 'lo'}).count(), 2)  # noqa
        self.assertEqual(M.query(**{'author.username__match': 'Louise'}).count(), 2)  # noqa

        self.assertEqual(M.query(**{'category.name__prefix': 'tes'}).count(), 2)  # noqa
        self.assertEqual(M.query(**{'category.name__term': 'tes'}).count(), 0)
        self.assertEqual(M.query(**{'category.name__term': 'tests'}).count(), 2)  # noqa

        """
        term    Term query
        terms   Terms query
        in  Terms query
        match   Match query [1]
        prefix  Prefix query [2]
        gt, gte, lt, lte    Range query
        range   Range query [4]
        fuzzy   Fuzzy query
        wildcard    Wildcard query
        match_phrase    Match phrase query [1]
        query_string    Querystring query [3]
        distance
        """


class FilterTestCase(BaseTest):
    fixtures = ['test_data']

    def test_filter_term_string(self):
        search_terms = {'subject': 'amazing'}

        filter_set = ElasticutilsFilterSet(search_fields=self.search_fields,
                                           search_actions=None,
                                           search_terms=search_terms,
                                           mapping_type=self.mapping_type,
                                           queryset=M.query(),
                                           default_action=None)

        # Test formed filter
        subject_filter = filter_set.get_filter('subject', 'amazing').__repr__()
        self.assertEqual(F(**{'subject': 'amazing'}).__repr__(), subject_filter)  # noqa

        filtered_qs = filter_set.qs

        self.assertEqual(filtered_qs.count(), 1)

    def test_filter_prefix_or_startswith(self):
        default_action = 'prefix'
        search_terms = {'category.name': 'tes'}
        filter_set = ElasticutilsFilterSet(search_fields=self.search_fields,
                                           search_actions=None,
                                           search_terms=search_terms,
                                           mapping_type=self.mapping_type,
                                           queryset=M.query(),
                                           default_action=default_action)

        self.assertEqual(filter_set.qs.count(), 2)

        search_actions = {'category.name': 'prefix'}
        filter_set = ElasticutilsFilterSet(search_fields=self.search_fields,
                                           search_actions=search_actions,
                                           search_terms=search_terms,
                                           mapping_type=self.mapping_type,
                                           queryset=M.query(),
                                           default_action=None)

        subject_filter = filter_set.get_filter('category.name', 'tes').__repr__()  # noqa
        self.assertEqual(F(**{'category.name__prefix': 'tes'}).__repr__(), subject_filter)  # noqa

        default_action = 'startswith'
        search_terms = {'category.name': 'tes'}
        filter_set = ElasticutilsFilterSet(search_fields=self.search_fields,
                                           search_actions=None,
                                           search_terms=search_terms,
                                           mapping_type=self.mapping_type,
                                           queryset=M.query(),
                                           default_action=default_action)

        self.assertEqual(filter_set.qs.count(), 2)
        self.assertEqual(filter_set.count, 2)

        search_actions = {'category.name': 'startswith'}
        filter_set = ElasticutilsFilterSet(search_fields=self.search_fields,
                                           search_actions=search_actions,
                                           search_terms=search_terms,
                                           mapping_type=self.mapping_type,
                                           queryset=M.query(),
                                           default_action='prefix')

        self.assertEqual(filter_set.qs.count(), 2)
        self.assertEqual(filter_set.count, 2)

        subject_filter = filter_set.get_filter('category.name', 'tes').__repr__()  # noqa
        self.assertEqual(F(**{'category.name__startswith': 'tes'}).__repr__(), subject_filter)  # noqa

    """def test_filter_in(self):
        # TODO

    def test_filter_range(self):
        # TODO

    def test_filter_distance(self):
        # TODO

    def test_filter_ids(self):
        ids = [1, 2]

    def test_filter_nested(self):
        # TODO

    def test_filter_multiple_fields(self):
        # TODO"""
