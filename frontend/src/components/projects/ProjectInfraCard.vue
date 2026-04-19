<script setup lang="ts">
import DataRow from "@/components/ui/DataRow.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>infra</MonoLabel>
    <div v-if="project.infra" class="mt-3 space-y-0.5">
      <DataRow v-if="project.infra.domain_primary" label="domain">
        <span class="font-mono">{{ project.infra.domain_primary }}</span>
      </DataRow>
      <DataRow v-if="project.infra.server_alias" label="server">
        <span class="font-mono">{{ project.infra.server_alias }}</span>
      </DataRow>
      <DataRow v-if="project.infra.dns_provider" label="dns">
        {{ project.infra.dns_provider }}
      </DataRow>
      <DataRow v-if="project.infra.db_host" label="db">
        <span class="font-mono">{{ project.infra.db_host }}</span>
      </DataRow>
      <DataRow v-if="project.infra.cdn" label="cdn">
        {{ project.infra.cdn }}
      </DataRow>
    </div>
    <p v-else class="text-small text-fg-muted italic mt-2">— no infra configured —</p>
  </section>
</template>
