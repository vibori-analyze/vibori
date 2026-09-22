<template>
  <div>
    <a class="skip-link" href="#main">Перейти к содержимому</a>
    <header>
      <NuxtLink to="/" class="brand">ВЫБОРЫ<span>.</span></NuxtLink>
      <p>Открытый архив результатов</p>
      <nav aria-label="Основная навигация"><NuxtLink to="/#catalog">Найти участок ↗</NuxtLink></nav>
    </header>
    <main id="main"><slot /></main>
    <footer>ВЫБОРЫ. <span>Открытые результаты · Проверяемые источники</span></footer>
  </div>
</template>
