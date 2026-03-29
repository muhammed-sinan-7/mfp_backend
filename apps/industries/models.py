from django.db import models

from common.models import BaseModel


class Industry(BaseModel):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Tag(BaseModel):
    name = models.CharField(max_length=150)
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
