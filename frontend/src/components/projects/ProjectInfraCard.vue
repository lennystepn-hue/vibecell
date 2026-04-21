<script setup lang="ts">
import CopyableValue from "@/components/ui/CopyableValue.vue";
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
        <CopyableValue :value="project.infra.domain_primary" mono small />
      </DataRow>
      <DataRow v-if="project.infra.server_alias" label="server">
        <CopyableValue :value="project.infra.server_alias" mono small />
      </DataRow>
      <DataRow v-if="project.infra.dns_provider" label="dns">
        <CopyableValue :value="project.infra.dns_provider" small />
      </DataRow>
      <DataRow v-if="project.infra.db_host" label="db">
        <CopyableValue :value="project.infra.db_host" mono small />
      </DataRow>
      <DataRow v-if="project.infra.cdn" label="cdn">
        <CopyableValue :value="project.infra.cdn" small />
      </DataRow>
    </div>
    <p v-else class="text-small text-fg-muted italic mt-2">— no infra configured —</p>
  </section>
</template>
