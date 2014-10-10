"""Base mapping module for easier specific usage."""
from django.conf import settings

from elasticutils.contrib.django import MappingType
from elasticutils.contrib.django import Indexable

from django_esutils import tasks


class SearchMappingType(MappingType, Indexable):
    """Base class that implements MappingType and Indexable Elasticutils class
    plus some helpers:

        - compute mapping type name according model name
        - extract document 'magically' according mapping and model fields

    """

    id_field = 'pk'

    @classmethod
    def get_index(cls):
        """Returns default peopleask index name from settings."""
        return settings.ES_INDEX_DEFAULT

    @classmethod
    def get_mapping_type_name(cls):
        """Returns model name by default for mapping type name."""
        return cls.get_model()._meta.model_name

    @classmethod
    def doc_type(cls):
        """Shortcuts for easy es base use."""
        return cls.get_mapping_type_name()

    @classmethod
    def get_field_mapping(cls):
        raise NotImplemented('Implement this to speficy the fields to map.')

    @classmethod
    def get_mapping(cls):
        """Returns ES mapping spec including get_field_mapping result."""
        return {
            '_all': {
                'enabled': settings.ES_SOURCE_ENABLED,
            },
            '_source': {
                'enabled': settings.ES_SOURCE_ENABLED,
            },
            'properties': cls.get_field_mapping(),
        }

    @classmethod
    def extract_document(cls, obj_id, obj=None):
        """Returns json doc to index for a given pkand the current mapping."""

        # retrieve object if not passed
        if obj is None:
            obj = cls.get_model().get(id=obj_id)

        # shortcut
        mapping_keys = [cls.id_field] + cls.get_field_mapping().keys()

        # build doc according mapping keys and obj values
        doc = {}
        for k in mapping_keys:
            # split key if is a 2 level key or one level key, ex.:
            #   - 'id', None if k == 'id'
            #   - 'author', 'first_name' if k == 'author__first_name'
            k_1, k_2 = (k, None) if '__' not in k else k.split('__')

            # update the doc according splitted key, ex.: {
            #     'id': obj.id,
            # }
            # ... or if is a 2 level key: {
            #     'author__first_name': obj.author.first_name,
            # }
            doc[k] = getattr(obj, k_1)
            if k_2:
                doc[k] = getattr(doc[k], k_2)

            # ensure pk serialization
            if k == cls.id_field:
                doc[k] = str(doc[k])

        return doc

    @classmethod
    def generate_mappings(cls):
        return dict([(doc_type, {
        }) for doc_type in settings.ES_DOC_TYPES])

    @classmethod
    def create_index(cls, es=None, index=None, mappings=None):

        # ensure es and index values
        es = es or cls.get_es()
        index = index or cls.get_index()

        if not es.indices.exists(index):
            # passed or default mappings
            mappings = mappings or cls.generate_mappings()
            # do create
            es.indices.create(index, body={
                'settings': settings.ES_INDEX_SETTINGS,
                'mappings': mappings,
            })
            # refresh
            # cls.refresh_index()

    @classmethod
    def update_mapping(cls, es=None, index=None, doc_type=None, mapping=None,
                       delete_previous_mapping=True):
        """Creates index with current mapping if not exist yet."""
        # ensure es and index values
        es = es or cls.get_es()
        index = index or cls.get_index()
        doc_type = doc_type or cls.doc_type()
        mapping = mapping or cls.get_mapping()

        # create index if not exist yet
        cls.create_index(es=es, index=index)

        # delete previous mapping if specified
        if delete_previous_mapping:
            es.indices.delete_mapping(index, doc_type)

        # update mapping if needed
        es.indices.put_mapping(doc_type, {
            doc_type: mapping
        }, index=index)

        # refresh
        # cls.refresh_index()

    @classmethod
    def es_index(cls, sender, instance, **kwargs):
        tasks.index_objects.delay(cls, [instance.uuid], id_field=cls.id_field)

    @classmethod
    def es_unindex(cls, sender, instance, **kwargs):
        tasks.unindex_objects.delay(cls, [instance.uuid])